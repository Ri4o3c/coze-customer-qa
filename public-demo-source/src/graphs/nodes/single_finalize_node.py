import json
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import FinalizeInput, FinalizeOutput

CATEGORY_ROUTE = {
    "物流配送": "物流客服",
    "退款退货": "售后客服",
    "商品质量": "商品售后",
    "订单与支付": "订单客服",
    "其他问题": "综合客服",
}
RULE_NAMES = {"R01": "客服不得辱骂、嘲讽或贬低客户",
              "R02": "客服不得索取客户的账户密码、支付密码或支付验证码",
              "R03": "退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点"}


def finalize_node(state: FinalizeInput, config: RunnableConfig, runtime: Runtime[Context]) -> FinalizeOutput:
    """
    title: 结果与中文报告
    desc: 汇总质检结果，计算最终质检状态、复核标记、路由去向，并生成中文质检报告与结果JSON（仅给建议，不建单/不退款/不发消息）。
    """
    manual_input = not state.validation_valid
    manual_rules = not state.rules_ok

    reasons: List[str] = []
    if isinstance(state.review_reasons, list):
        reasons = [str(x) for x in state.review_reasons]
    if manual_input:
        reasons.append("输入校验未通过：" + (state.validation_error or "记录无效"))
    if manual_rules:
        reasons.append("规则知识库完整性校验未通过：" + (state.rules_reason or "缺少规则"))

    model_needs_review = bool(state.needs_review)
    needs_review = manual_input or manual_rules or model_needs_review

    category = state.category if state.category_valid else ""
    suggested = CATEGORY_ROUTE.get(category, "综合客服")
    route = "人工复核队列" if needs_review else suggested

    qc_status = state.qc_status
    if manual_input or manual_rules:
        qc_status = "undetermined"

    checks = state.checks if isinstance(state.checks, dict) else {}

    result: Dict[str, Any] = {
        "schema_version": 1,
        "ticket_id": state.ticket_id,
        "category": category,
        "category_valid": state.category_valid,
        "category_confidence": state.category_confidence,
        "category_evidence": state.category_evidence,
        "summary": state.summary,
        "checks": checks,
        "qc_status": qc_status,
        "needs_review": needs_review,
        "review_reasons": reasons,
        "route": route,
        "suggested_route": suggested,
        "action": "suggest_only",
        "validation": state.validation,
        "semantic_review": state.semantic_review,
    }

    result_json = json.dumps(result, ensure_ascii=False)

    # ---------- 中文报告 ----------
    lines: List[str] = []
    lines.append(f"== 客服质检与工单分流报告（ticket_id: {state.ticket_id or '（缺失）'}）==")
    lines.append(f"问题分类：{category or '（未分类）'}（{state.category_confidence:.2f}）")
    lines.append(f"分类有效：{'是' if state.category_valid else '否'}")
    if state.category_evidence:
        for ev in state.category_evidence:
            midx = ev.get("message_index")
            lines.append(f"  分类证据[消息{midx}]：{ev.get('quote')}")
    lines.append(f"摘要：{state.summary or '（无）'}")
    lines.append("质检状态：" + qc_status)
    lines.append("是否需要人工复核：" + ("是" if needs_review else "否"))
    if reasons:
        lines.append("复核原因：")
        for r in reasons:
            lines.append(f"  - {r}")
    lines.append("路由去向：建议" + suggested + ("（转人工复核队列）" if needs_review else ""))
    lines.append("")
    lines.append("逐规则质检证据：")
    if checks:
        for rid in ["R01", "R02", "R03"]:
            c = checks.get(rid)
            if not isinstance(c, dict):
                continue
            lines.append(f"[{rid}] {RULE_NAMES.get(rid, '')}")
            lines.append(f"  判定：{c.get('status')} | policy原文：{c.get('rule_quote')}")
            lines.append(f"  依据：{c.get('reason')}")
            evs = c.get("evidence") or []
            if evs:
                for ev in evs:
                    lines.append(f"    证据[消息{ev.get('message_index')}·客服]：{ev.get('quote')}")
            else:
                lines.append("    证据：（无）")
    else:
        lines.append("（无可校验规则证据，已整体转人工复核）")
    lines.append("说明：本流程仅提供质检与分流建议（action=suggest_only），不会实际建单、退款或发送任何消息；引用存在性已由代码校验，语义是否成立仍需人工确认。")
    report = "\n".join(lines)

    return FinalizeOutput(
        result_json=result_json,
        report=report,
        needs_review=needs_review,
        ticket_id=state.ticket_id,
        qc_status=qc_status,
        category=category,
    )