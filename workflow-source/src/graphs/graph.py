from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    ValidRouteState,
    RulesRouteState,
    ReviewRouteState,
)
from graphs.nodes.single_validate_node import validate_node
from graphs.nodes.single_kb_retrieval_node import kb_retrieval_node
from graphs.nodes.single_rule_check_node import rule_check_node
from graphs.nodes.single_llm_extraction_node import llm_extraction_node
from graphs.nodes.single_json_validation_node import json_validation_node
from graphs.nodes.single_finalize_node import finalize_node


def route_valid(state: ValidRouteState) -> str:
    """
    title: 有效则继续
    desc: 输入校验通过则进入知识库检索；未通过则转入人工兜底。
    """
    if state.validation_valid:
        return "continue"
    return "manual"


def route_rules(state: RulesRouteState) -> str:
    """
    title: 规则完整则校验
    desc: 规则完整性校验通过则进入大模型提取；缺规则或冲突则转入人工兜底。
    """
    if state.rules_ok:
        return "continue"
    return "manual"


def route_review(state: ReviewRouteState) -> str:
    """
    title: 复核分支
    desc: 依据needs_review分支：需复核与正常两条路径最终都汇聚到结果与中文报告节点（最终结果里体现复核标记）。
    """
    if state.needs_review:
        return "review"
    return "normal"


# ---- 单条主流程 customer_qa_single_v1 ----
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

builder.add_node("validate", validate_node)
builder.add_node("kb_retrieval", kb_retrieval_node)
builder.add_node("rule_check", rule_check_node)
builder.add_node("llm_extraction", llm_extraction_node,
                 metadata={"type": "agent", "llm_cfg": "config/customer_qa_single_llm_cfg.json"})
builder.add_node("json_validation", json_validation_node)
builder.add_node("finalize", finalize_node)

builder.set_entry_point("validate")

# 输入校验选择器
builder.add_conditional_edges(
    source="validate",
    path=route_valid,
    path_map={"continue": "kb_retrieval", "manual": "finalize"},
)
builder.add_edge("kb_retrieval", "rule_check")

# 规则完整性校验选择器
builder.add_conditional_edges(
    source="rule_check",
    path=route_rules,
    path_map={"continue": "llm_extraction", "manual": "finalize"},
)
builder.add_edge("llm_extraction", "json_validation")

# 复核分支选择器（两条分支最终都进入 finalize）
builder.add_conditional_edges(
    source="json_validation",
    path=route_review,
    path_map={"review": "finalize", "normal": "finalize"},
)
builder.add_edge("finalize", END)

main_graph = builder.compile()