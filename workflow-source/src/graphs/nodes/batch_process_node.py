import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import BatchProcessInput, BatchProcessOutput
from graphs.graph import main_graph as single_main_graph

MAX_CONCURRENCY = 2
MAX_ITEMS = 50


def _run_single(record_json: str) -> Dict[str, Any]:
    try:
        out = single_main_graph.invoke({"record_json": record_json})
        if isinstance(out, dict):
            return out
        return {}
    except Exception as e:
        return {"_batch_error": f"{e}"}


def batch_process_node(state: BatchProcessInput, config: RunnableConfig, runtime: Runtime[Context]) -> BatchProcessOutput:
    """
    title: 批处理调用单条流程
    desc: 并发批量调用已发布的单条质检流程 customer_qa_single_v1，按ticket_id关联结果而非完成顺序；漏项补unknown人工记录，重复结果标复核。
    """
    items: List[Dict[str, Any]] = state.items or []
    results: List[Dict[str, Any]] = []

    if not items:
        return BatchProcessOutput(results=[])

    # 按 ticket_id 关联
    by_id: Dict[str, Dict[str, Any]] = {}
    duplicates_map: Dict[str, int] = {}
    for it in items:
        tid = str(it.get("ticket_id", ""))
        duplicated = tid in by_id
        if duplicated:
            duplicates_map[tid] = duplicates_map.get(tid, 0) + 1

    lock = threading.Lock()
    processed: Dict[str, List[Dict[str, Any]]] = {}

    def work(it: Dict[str, Any]) -> None:
        tid = str(it.get("ticket_id", ""))
        record_json = str(it.get("record_json", ""))
        out = _run_single(record_json)
        out["_messages"] = _extract_messages(record_json)
        with lock:
            processed.setdefault(tid, []).append(out)

    # 并发2，次数上限50
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as ex:
        futs = [ex.submit(work, it) for it in items[:MAX_ITEMS]]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                pass

    # 按原始顺序产出结果记录（按ticket_id关联，而非完成顺序）
    for it in items:
        tid = str(it.get("ticket_id", ""))
        bucket = processed.get(tid, [])
        if not bucket:
            # 漏项：补unknown人工记录
            results.append(_fallback_unknown(tid, "批次执行结果缺失，补unknown人工记录", _extract_messages(str(it.get("record_json", "")))))
            continue
        rec = _normalize_single_result(tid, bucket[0])
        if len(bucket) > 1:
            rec["duplicate_result"] = True
            rec["needs_review"] = True
            rec["review_reasons"] = list(rec.get("review_reasons") or []) + ["该记录存在重复处理结果，标记复核"]
        results.append(rec)

    return BatchProcessOutput(results=results)


def _extract_messages(record_json: str) -> List[Dict[str, Any]]:
    try:
        obj = json.loads(record_json)
        if isinstance(obj, dict):
            msgs = obj.get("messages")
            if isinstance(msgs, list):
                return [{"role": str(m.get("role", "")), "text": str(m.get("text", ""))} for m in msgs if isinstance(m, dict)]
    except Exception:
        pass
    return []


def _fallback_unknown(tid: str, reason: str, messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "ticket_id": tid,
        "result_json": json.dumps({}, ensure_ascii=False),
        "report": "",
        "needs_review": True,
        "qc_status": "undetermined",
        "category": "",
        "category_valid": False,
        "checks": {},
        "review_reasons": [reason],
        "error": reason,
        "messages": messages or [],
    }


def _normalize_single_result(tid: str, out: Dict[str, Any]) -> Dict[str, Any]:
    messages = out.get("_messages") or []
    if "_batch_error" in out:
        reason = f"单条流程执行异常: {out.get('_batch_error')}"
        return _fallback_unknown(tid, reason, messages)
    result_json = str(out.get("result_json", ""))
    report = str(out.get("report", ""))
    needs_review = bool(out.get("needs_review", False))
    category = ""
    category_valid = False
    qc_status = "undetermined"
    checks: Dict[str, Any] = {}
    review_reasons: List[str] = []
    try:
        parsed = json.loads(result_json) if result_json else {}
        if isinstance(parsed, dict):
            category = str(parsed.get("category", ""))
            category_valid = bool(parsed.get("category_valid", False))
            qc_status = str(parsed.get("qc_status", "undetermined"))
            checks = parsed.get("checks") or {}
            rr = parsed.get("review_reasons") or []
            review_reasons = [str(x) for x in rr] if isinstance(rr, list) else []
    except Exception:
        pass
    return {
        "ticket_id": tid,
        "result_json": result_json,
        "report": report,
        "needs_review": needs_review,
        "qc_status": qc_status,
        "category": category,
        "category_valid": category_valid,
        "checks": checks,
        "review_reasons": review_reasons,
        "messages": messages,
    }