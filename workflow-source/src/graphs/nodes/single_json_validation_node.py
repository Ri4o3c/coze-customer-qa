import json
import math
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import JsonValidationInput, JsonValidationOutput

CATEGORY_ROUTE = {
    "物流配送": "物流客服",
    "退款退货": "售后客服",
    "商品质量": "商品售后",
    "订单与支付": "订单客服",
    "其他问题": "综合客服",
}
RULE_IDS = ["R01", "R02", "R03"]
VALID_STATUS = {"pass", "fail", "unknown"}


def _strip_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _evid_valid(ev: Any, messages: List[Dict[str, Any]], only_agent: bool, issues: List[str],
                required_role: str = "") -> bool:
    if not isinstance(ev, dict):
        issues.append("证据项不是对象")
        return False
    midx = ev.get("message_index")
    quote = ev.get("quote")
    if not isinstance(midx, int) or isinstance(midx, bool) or midx < 0 or midx >= len(messages):
        issues.append(f"message_index必须是0起整数下标且在范围内: {midx!r}")
        return False
    if not isinstance(quote, str) or not quote.strip():
        issues.append(f"message_index {midx} 的quote为空或非字符串")
        return False
    msg = messages[midx]
    role = str(msg.get("role", ""))
    if only_agent and role != "agent":
        issues.append(f"质检证据只允许来自agent消息，但index {midx} 角色为 {role}")
        return False
    if required_role == "customer" and role != "customer":
        issues.append(f"分类证据只允许来自customer消息，但index {midx} 角色为 {role}")
        return False
    if quote not in str(msg.get("text", "")):
        issues.append(f"引用不是连续原文（index {midx}）：{quote!r}")
        return False
    return True


def json_validation_node(state: JsonValidationInput, config: RunnableConfig, runtime: Runtime[Context]) -> JsonValidationOutput:
    """
    title: 代码校验JSON/证据/规则
    desc: 校验模型输出的JSON字段、证据引用是否连续原文、规则引用是否与知识库policy一致；任一类异常整条降级unknown并转人工复核。
    """
    messages: List[Dict[str, Any]] = state.messages or []
    issues: List[str] = []
    degraded: bool = False

    if not state.llm_ok or not (state.llm_raw or "").strip():
        degraded = True
        issues.append("大模型调用失败或返回为空")

    obj: Any = None
    if not degraded:
        try:
            obj = json.loads(_strip_json(state.llm_raw or ""))
            if not isinstance(obj, dict):
                degraded = True
                issues.append("模型输出JSON不是对象")
        except Exception as e:
            degraded = True
            issues.append(f"无效JSON: {e}")

    category = ""
    category_confidence = 0.0
    category_evidence: List[Dict[str, Any]] = []
    summary = ""
    checks: Dict[str, Any] = {}
    model_needs_review = False
    model_reasons: List[str] = []

    if not degraded:
        category = obj.get("category")
        if not isinstance(category, str) or not category.strip():
            degraded = True
            issues.append("缺少category字段")
        else:
            category = category.strip()
        conf = obj.get("category_confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not math.isfinite(float(conf)):
            degraded = True
            issues.append("category_confidence必须是有限数字")
        else:
            conf = float(conf)
            if not (0.0 <= conf <= 1.0):
                degraded = True
                issues.append(f"category_confidence越界: {conf}")
            else:
                category_confidence = conf
        ev = obj.get("category_evidence")
        if not isinstance(ev, list):
            degraded = True
            issues.append("category_evidence必须是数组")
        else:
            # 代码不变量：确认分类必须至少有1条customer原文证据，不接受空数组
            if len(ev) == 0:
                degraded = True
                issues.append("category_evidence为空数组：确认分类须至少有1条customer原文证据")
            else:
                cat_ok = True
                for it in ev:
                    # 分类证据必须是客户customer连续原文
                    if not _evid_valid(it, messages, False, issues, required_role="customer"):
                        cat_ok = False
                if cat_ok:
                    category_evidence = ev
                else:
                    degraded = True
        sm = obj.get("summary")
        if isinstance(sm, str) and sm.strip():
            summary = sm.strip()
        else:
            degraded = True
            issues.append("summary缺失或为空")
        chk = obj.get("checks")
        if not isinstance(chk, dict):
            degraded = True
            issues.append("checks缺失或不是对象")
        else:
            # 必须恰好包含 R01/R02/R03，缺任一或重复规则键一律降级
            keys = set(chk.keys())
            if keys != set(RULE_IDS):
                degraded = True
                issues.append(f"checks必须恰好包含R01/R02/R03，实际: {sorted(keys)}")
            else:
                checks_ok = True
                for rid in RULE_IDS:
                    c = chk.get(rid)
                    if not isinstance(c, dict):
                        degraded = True
                        issues.append(f"check {rid} 缺失或不是对象")
                        checks_ok = False
                        continue
                    c_rid = c.get("rule_id")
                    c_status = c.get("status")
                    c_quote = c.get("rule_quote")
                    c_reason = c.get("reason")
                    c_ev = c.get("evidence")
                    if str(c_rid) != rid:
                        degraded = True
                        issues.append(f"check {rid} 的rule_id与键不符: {c_rid!r}")
                        checks_ok = False
                    if c_status not in VALID_STATUS:
                        degraded = True
                        issues.append(f"check {rid} status非法: {c_status!r}")
                        checks_ok = False
                    if not isinstance(c_quote, str) or not c_quote.strip():
                        degraded = True
                        issues.append(f"check {rid} 缺少rule_quote")
                        checks_ok = False
                    else:
                        expected_policy = [str(r.get("policy", "")) for r in state.rules
                                           if str(r.get("rule_id", "")) == rid]
                        # 严格逐字校验：rule_quote 必须完整等于该rule_id的policy原文（含标点），不接受缩写子串
                        if not expected_policy or c_quote.strip() != expected_policy[0].strip():
                            degraded = True
                            issues.append(f"check {rid} 的rule_quote未逐字匹配规则库policy原文(假引用或标点差异): {c_quote!r}")
                            checks_ok = False
                    if not isinstance(c_reason, str) or not c_reason.strip():
                        degraded = True
                        issues.append(f"check {rid} 缺少reason")
                        checks_ok = False
                    if not isinstance(c_ev, list):
                        degraded = True
                        issues.append(f"check {rid} evidence必须是数组")
                        checks_ok = False
                    else:
                        if (c_status in ("pass", "fail")) and len(c_ev) == 0:
                            degraded = True
                            issues.append(f"check {rid} {c_status}必须有至少一条客服原文证据")
                            checks_ok = False
                        ev_ok = True
                        for it in c_ev:
                            if not _evid_valid(it, messages, True, issues):
                                ev_ok = False
                        if not ev_ok:
                            checks_ok = False
                if checks_ok:
                    checks = chk
                else:
                    # 任一条check证据校验失败：整条降级unknown并人工复核
                    degraded = True

        nr = obj.get("needs_review")
        if not isinstance(nr, bool):
            degraded = True
            issues.append("needs_review必须是Boolean")
        else:
            model_needs_review = nr
        rr = obj.get("review_reasons")
        if not isinstance(rr, list):
            degraded = True
            issues.append("review_reasons必须是数组")
        else:
            model_reasons = [str(x) for x in rr if isinstance(x, str) and str(x).strip()]

    # 非字符串分类无法用于路由：统一置空并标记降级（防御非字符串，如 []/{}）
    if not isinstance(category, str):
        degraded = True
        issues.append(f"category必须是字符串: {type(category).__name__}")
        category = ""

    category_valid = category in CATEGORY_ROUTE
    if category_valid and not degraded:
        pass
    elif not degraded and category and not category_valid:
        # 分类不属于五类之一：无法可靠路由，转人工
        degraded = True
        issues.append(f"category不属于合法五类: {category}")

    # 计算 qc_status 与 needs_review
    if degraded:
        checks = {}
        for rid in RULE_IDS:
            expected_policy = ""
            for r in state.rules:
                if str(r.get("rule_id", "")) == rid:
                    expected_policy = str(r.get("policy", ""))
            checks[rid] = {
                "rule_id": rid,
                "status": "unknown",
                "rule_quote": expected_policy,
                "reason": "；".join(issues) or "整条降级unknown",
                "evidence": [],
            }
        qc_status = "undetermined"
        needs_review = True
        review_reasons = ["代码校验异常，整条降级unknown并人工复核"] + [f"({i+1}){x}" for i, x in enumerate(issues)]
        if model_reasons:
            review_reasons = review_reasons + model_reasons
    else:
        statuses = [str(checks.get(r, {}).get("status", "unknown")) for r in RULE_IDS]
        has_fail = "fail" in statuses
        has_unknown = "unknown" in statuses
        if has_fail:
            qc_status = "violation"
        elif has_unknown:
            qc_status = "undetermined"
        else:
            qc_status = "pass"

        conf_low = category_confidence < 0.75
        # 代码强制不变量：任一规则status=unknown时，必须needs_review=true（不依赖模型自报复核）
        force_review_unknown = has_unknown
        needs_review = model_needs_review or conf_low or (not category_valid) or force_review_unknown
        review_reasons = list(model_reasons)
        if force_review_unknown:
            review_reasons.append("存在任一规则判定为unknown，代码强制人工复核")
        if conf_low:
            review_reasons.append(f"分类置信度{category_confidence:.2f}低于0.75")
        if not category_valid:
            review_reasons.append("分类不属于合法五类")

    validation = {
        "valid_json": not degraded,
        "fields_complete": not degraded,
        "evidence_verified": not degraded,
        "roles_checked": "角色仅customer/agent已在输入校验阶段完成",
        "issues": issues,
        "note": "引用存在性已由代码校验，语义是否成立仍需人工确认",
    }
    semantic_review = {
        "needs_semantic_review": needs_review,
        "confidence_below_threshold": (not degraded) and category_confidence < 0.75,
        "model_requested_review": model_needs_review if not degraded else False,
        "degraded": degraded,
        "manual_confirmation_pending": "代码验证引用存在不等于语义已人工确认",
    }

    return JsonValidationOutput(
        category=category,
        category_valid=category_valid,
        category_confidence=category_confidence,
        category_evidence=category_evidence,
        summary=summary,
        checks=checks,
        needs_review=needs_review,
        review_reasons=review_reasons,
        qc_status=qc_status,
        validation=validation,
        semantic_review=semantic_review,
    )