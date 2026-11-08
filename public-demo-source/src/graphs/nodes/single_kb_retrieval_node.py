import re
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import KnowledgeClient, Config
from graphs.state import KbRetrievalInput, KbRetrievalOutput

RULES_DATASET = "customer_service_rules_v1"
# 固定查询：同时含 R01 R02 R03，强制检索这三条，不由模型选择是否检索
FIXED_QUERY = ("R01 客服不得辱骂嘲讽贬低客户 "
               "R02 客服不得索取账户密码支付密码支付验证码 "
               "R03 退款须经售后审核预计1至3个工作日原路退回不得保证到账时点")


def _extract_rule(content: str) -> Dict[str, Any]:
    """从KB chunk内容解析规则，返回 {rule_id, version, policy}；解析失败返回None"""
    try:
        m = re.search(r"(R0[123])", content)
        if not m:
            return None
        rule_id = m.group(1)
        v = re.search(r"版本\s*([0-9]+(?:\.[0-9]+)*)", content)
        version = v.group(1) if v else "1.0"
        # policy 取版本号之后的连续文本：仅去除边界空白，保留完整标点（含句号），供逐字比对
        if v:
            policy = content[v.end():].strip()
        else:
            policy = content
        if not policy:
            return None
        return {"rule_id": rule_id, "version": version, "policy": policy}
    except Exception:
        return None


def kb_retrieval_node(state: KbRetrievalInput, config: RunnableConfig, runtime: Runtime[Context]) -> KbRetrievalOutput:
    """
    title: 规则知识库检索
    desc: 用固定查询强制检索商家规则库 customer_service_rules_v1 中的R01/R02/R03三条规则，不由模型选择是否检索。
    integrations: 知识库检索
    """
    rules: List[Dict[str, Any]] = []
    error: str = ""
    try:
        client = KnowledgeClient(config=Config(), ctx=runtime.context)
        response = client.search(query=FIXED_QUERY, table_names=[RULES_DATASET], top_k=8)
        if response is None or getattr(response, "code", 0) != 0:
            msg = getattr(response, "msg", "") if response is not None else ""
            error = f"知识库检索失败: {msg}"
            return KbRetrievalOutput(rules=[], retrieval_error=error)
        chunks = getattr(response, "chunks", []) or []
        seen = {}
        for chunk in chunks:
            content = getattr(chunk, "content", "") or ""
            parsed = _extract_rule(content)
            if parsed:
                seen.setdefault(parsed["rule_id"], parsed)
        rules = list(seen.values())
    except Exception as e:
        error = f"知识库检索异常: {e}"
        return KbRetrievalOutput(rules=[], retrieval_error=error)
    return KbRetrievalOutput(rules=rules, retrieval_error=error)