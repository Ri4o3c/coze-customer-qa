from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import RuleCheckInput, RuleCheckOutput

EXPECTED_RULES = {"R01", "R02", "R03"}


def rule_check_node(state: RuleCheckInput, config: RunnableConfig, runtime: Runtime[Context]) -> RuleCheckOutput:
    """
    title: 规则完整性校验
    desc: 校验检索结果是否完整覆盖R01/R02/R03、版本为1.0且无同ID规则冲突；缺一条或同ID冲突即判定不通过并转人工，不凭常识补齐。
    """
    rules_in: List[Dict[str, Any]] = state.rules or []
    seen: Dict[str, Dict[str, Any]] = {}
    ok: bool = True
    reason: str = "规则覆盖完整"

    for r in rules_in:
        if not isinstance(r, dict):
            ok = False
            reason = "检索结果包含非规则结构，完整性校验失败"
            break
        rid = str(r.get("rule_id", "")).strip()
        policy = str(r.get("policy", "")).strip()
        version = str(r.get("version", "")).strip()
        if rid not in EXPECTED_RULES:
            ok = False
            reason = f"检索到未授权规则ID: {rid}，与规则库不符"
            break
        if not policy:
            ok = False
            reason = f"规则{rid}缺少policy原文"
            break
        if version and version not in ("1.0", "1.0.0"):
            ok = False
            reason = f"规则{rid}版本不是1.0: {version}"
            break
        if rid in seen:
            if seen[rid].get("policy", "").strip() != policy:
                ok = False
                reason = f"规则{rid}出现同ID不同policy的冲突"
                break
        seen[rid] = {"rule_id": rid, "version": version or "1.0", "policy": policy}

    if ok:
        missing = EXPECTED_RULES - set(seen.keys())
        if missing:
            ok = False
            reason = f"规则知识库检索不完整，缺失规则: {sorted(missing)}，转人工复核，不凭常识补齐"
        else:
            # 规范化排序输出
            ordered = [seen[k] for k in ["R01", "R02", "R03"] if k in seen]
            return RuleCheckOutput(rules=ordered, rules_ok=True, rules_reason=reason)

    return RuleCheckOutput(rules=list(seen.values()), rules_ok=False, rules_reason=reason)