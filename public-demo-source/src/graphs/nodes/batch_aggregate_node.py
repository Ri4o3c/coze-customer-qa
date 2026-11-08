import json
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import BatchAggregateInput, BatchAggregateOutput


def _status_of(rec: Dict[str, Any]) -> str:
    return str(rec.get("qc_status", "undetermined"))


REQUIRED_FIELDS = [
    "schema_version", "ticket_id", "category", "category_valid", "category_confidence",
    "category_evidence", "summary", "checks", "qc_status", "needs_review",
    "review_reasons", "route", "suggested_route", "action", "validation", "semantic_review",
]
REQUIRED_CHECK_SUB = ["rule_id", "status", "rule_quote", "reason", "evidence"]


def _revalidate_single(rec: Dict[str, Any]) -> List[str]:
    """校验单条结果完整结构与客户原文引用，返回问题列表；空列表表示通过。"""
    problems: List[str] = []
    raw = rec.get("result_json", "")
    try:
        obj = json.loads(raw) if raw else {}
    except Exception as e:
        return [f"result_json不是合法JSON: {e}"]
    if not isinstance(obj, dict):
        return ["result_json不是JSON对象"]
    missing = [f for f in REQUIRED_FIELDS if f not in obj]
    if missing:
        problems.append(f"缺少必需字段: {missing}")
    checks = obj.get("checks")
    if not isinstance(checks, dict):
        problems.append("checks缺失或不是对象")
    else:
        if set(checks.keys()) != {"R01", "R02", "R03"}:
            problems.append(f"checks必须恰好含R01/R02/R03，实际: {sorted(checks.keys())}")
        for rid in ("R01", "R02", "R03"):
            c = checks.get(rid)
            if not isinstance(c, dict):
                problems.append(f"check {rid} 不是对象")
                continue
            for sub in REQUIRED_CHECK_SUB:
                if sub not in c:
                    problems.append(f"check {rid} 缺少子字段 {sub}")
    # 客服原话：category_evidence 的 quote 必须命中 customer 消息原文
    messages = rec.get("messages") or []
    customer_msgs = [str(m.get("text", "")) for m in messages if str(m.get("role", "")) == "customer"]
    cat_ev = obj.get("category_evidence") or []
    if not isinstance(cat_ev, list):
        problems.append("category_evidence 不是数组")
    else:
        for ev in cat_ev:
            q = ev.get("quote") if isinstance(ev, dict) else None
            if not isinstance(q, str) or q.strip() == "":
                problems.append("category_evidence 存在无quote证据项")
            elif not any(q in t for t in customer_msgs):
                problems.append(f"分类证据quote未命中customer原文: {q!r}")
    return problems


def batch_aggregate_node(state: BatchAggregateInput, config: RunnableConfig, runtime: Runtime[Context]) -> BatchAggregateOutput:
    """
    title: 批量结果聚合
    desc: 按ticket_id关联统计total/pass/violation/undetermined/review/category/rule违规等；逐条复验单条完整结构及客服原话，异常不计pass并转人工。
    """
    results: List[Dict[str, Any]] = state.results or []
    total = len(results)

    pass_count = violation_count = undetermined_count = review_count = 0
    category_counts: Dict[str, int] = {}
    rule_violation_counts: Dict[str, int] = {}
    review_records: List[str] = []
    rows: List[Dict[str, Any]] = []
    recon_problems_count = 0

    for rec in results:
        tid = str(rec.get("ticket_id", ""))
        status = _status_of(rec)
        needs_review = bool(rec.get("needs_review", False))
        category = str(rec.get("category", ""))
        category_valid = bool(rec.get("category_valid", False))
        checks = rec.get("checks") or {}

        # 逐条复验单条完整结构与客服原话；异常则不作为有效pass/violation统计，转人工
        problems = _revalidate_single(rec)
        if problems:
            recon_problems_count += 1
            status = "undetermined"
            category = ""
            category_valid = False
            checks = {}
            needs_review = True
            reason_extra = "批量复验未通过：" + "；".join(problems)
            rr = rec.get("review_reasons") or []
            combined = [str(x) for x in rr] + [reason_extra] if isinstance(rr, list) else [reason_extra]
            rec = dict(rec)
            rec["review_reasons"] = combined
            rec["qc_status"] = "undetermined"
            review_records.append(f"{tid}: {reason_extra}")

        if status == "pass":
            pass_count += 1
        elif status == "violation":
            violation_count += 1
        else:
            undetermined_count += 1

        if needs_review:
            review_count += 1
            rr = rec.get("review_reasons") or []
            reason_txt = "；".join([str(x) for x in rr]) if isinstance(rr, list) else str(rr)
            review_records.append(f"{tid}: {reason_txt}")

        if category_valid:
            ckey = category if category else "无分类"
        else:
            ckey = "未确认" if category else "无分类"
        category_counts[ckey] = category_counts.get(ckey, 0) + 1

        for rid in ("R01", "R02", "R03"):
            c = checks.get(rid) if isinstance(checks, dict) else None
            if isinstance(c, dict) and str(c.get("status", "")) == "fail":
                rule_violation_counts[rid] = rule_violation_counts.get(rid, 0) + 1

        rows.append({
            "ticket_id": tid,
            "qc_status": status,
            "needs_review": needs_review,
            "category": category,
            "category_valid": category_valid,
            "revalidation_ok": (len(problems) == 0),
            "result_json": rec.get("result_json", ""),
        })

    summary: Dict[str, Any] = {
        "total": total,
        "pass_count": pass_count,
        "violation_count": violation_count,
        "undetermined_count": undetermined_count,
        "review_count": review_count,
        "category_counts": category_counts,
        "rule_violation_counts": rule_violation_counts,
        "review_records": review_records,
        "revalidation_failed_count": recon_problems_count,
        "results": rows,
    }
    summary_json = json.dumps(summary, ensure_ascii=False)

    lines: List[str] = []
    lines.append("== 客服质检与工单分流 - 批量汇总报告 ==")
    lines.append(f"总记录数 total：{total}")
    lines.append(f"pass：{pass_count} | violation：{violation_count} | undetermined：{undetermined_count}（合计={pass_count + violation_count + undetermined_count}）")
    lines.append(f"需人工复核 review_count：{review_count}（独立维度，不与前三者相加）")
    lines.append("分类统计：" + "; ".join(f"{k}={v}" for k, v in category_counts.items()))
    lines.append("规则违规统计：" + ("; ".join(f"{k}={v}" for k, v in rule_violation_counts.items()) if rule_violation_counts else "无"))
    lines.append("复核记录：")
    if review_records:
        for r in review_records:
            lines.append(f"  - {r}")
    else:
        lines.append("  （无）")
    lines.append("逐条结果：")
    for row in rows:
        lines.append(f"  {row['ticket_id']}: {row['qc_status']} | 分类={row['category']} | needs_review={row['needs_review']}")
    report = "\n".join(lines)

    return BatchAggregateOutput(summary_json=summary_json, report=report)