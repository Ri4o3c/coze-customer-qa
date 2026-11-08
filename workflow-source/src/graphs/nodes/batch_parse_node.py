import json
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import BatchParseInput, BatchParseOutput

MAX_BATCH = 50
MIN_BATCH = 1


def batch_parse_node(state: BatchParseInput, config: RunnableConfig, runtime: Runtime[Context]) -> BatchParseOutput:
    """
    title: 批量解析与校验
    desc: 解析records_json为1至50条记录数组，校验每条记录ID非空且全批唯一；缺ID或重复ID整批拒绝。
    """
    raw = (state.records_json or "").strip()
    items: List[Dict[str, Any]] = []
    ticket_ids: List[str] = []
    duplicate_ids: List[str] = []

    if not raw:
        return BatchParseOutput(parse_ok=False, parse_error="records_json为空", items=[], ticket_ids=[], duplicate_ids=[])
    try:
        arr = json.loads(raw)
    except Exception as e:
        return BatchParseOutput(parse_ok=False, parse_error=f"records_json不是合法JSON数组: {e}",
                                items=[], ticket_ids=[], duplicate_ids=[])
    if not isinstance(arr, list):
        return BatchParseOutput(parse_ok=False, parse_error="records_json必须是数组", items=[], ticket_ids=[], duplicate_ids=[])
    if not (MIN_BATCH <= len(arr) <= MAX_BATCH):
        return BatchParseOutput(parse_ok=False,
                                parse_error=f"记录数必须为{MIN_BATCH}至{MAX_BATCH}条，实际{len(arr)}条",
                                items=[], ticket_ids=[], duplicate_ids=[])

    seen = set()
    for i, rec in enumerate(arr):
        if not isinstance(rec, dict):
            return BatchParseOutput(parse_ok=False, parse_error=f"第{i}条记录不是JSON对象",
                                    items=[], ticket_ids=seen and list(seen) or [], duplicate_ids=duplicate_ids)
        tid = str(rec.get("ticket_id", "")).strip()
        if not tid:
            return BatchParseOutput(parse_ok=False, parse_error=f"第{i}条记录缺失ticket_id",
                                    items=[], ticket_ids=list(seen), duplicate_ids=duplicate_ids)
        if tid in seen:
            duplicate_ids.append(tid)
        seen.add(tid)

    if duplicate_ids:
        return BatchParseOutput(parse_ok=False,
                                parse_error=f"批次中ticket_id重复，整批拒绝: {sorted(set(duplicate_ids))}",
                                items=[], ticket_ids=list(seen), duplicate_ids=duplicate_ids)

    for rec in arr:
        tid = str(rec.get("ticket_id", "")).strip()
        item = {"ticket_id": tid, "record_json": json.dumps(rec, ensure_ascii=False)}
        items.append(item)
        ticket_ids.append(tid)

    return BatchParseOutput(parse_ok=True, parse_error="", items=items, ticket_ids=ticket_ids, duplicate_ids=[])