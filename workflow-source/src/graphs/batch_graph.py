from langgraph.graph import StateGraph, END
from graphs.state import (
    BatchGlobalState,
    BatchInput,
    BatchOutput,
    BatchRouteState,
)
from graphs.nodes.batch_parse_node import batch_parse_node
from graphs.nodes.batch_process_node import batch_process_node
from graphs.nodes.batch_aggregate_node import batch_aggregate_node


def route_batch(state: BatchRouteState) -> str:
    """
    title: 批次校验通过则处理
    desc: 批次解析校验通过则进入批处理；否则直接进入聚合节点（整批拒绝时输出错误汇总）。
    """
    if state.parse_ok:
        return "process"
    return "reject"


# ---- 批量流程 customer_qa_batch_v1（复用单条流程 customer_qa_single_v1） ----
builder = StateGraph(BatchGlobalState, input_schema=BatchInput, output_schema=BatchOutput)

builder.add_node("batch_parse", batch_parse_node)
builder.add_node("batch_process", batch_process_node)
builder.add_node("batch_aggregate", batch_aggregate_node)

builder.set_entry_point("batch_parse")

builder.add_conditional_edges(
    source="batch_parse",
    path=route_batch,
    path_map={"process": "batch_process", "reject": "batch_aggregate"},
)
builder.add_edge("batch_process", "batch_aggregate")
builder.add_edge("batch_aggregate", END)

batch_main_graph = builder.compile()