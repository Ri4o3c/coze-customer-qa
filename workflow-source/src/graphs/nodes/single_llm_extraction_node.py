import os
import json
from typing import List, Dict, Any
from jinja2 import Template
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, Config
from graphs.state import LlmInput, LlmOutput


def _safe_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if content and isinstance(content[0], str):
            return " ".join(content)
        parts = [item.get("text", "") for item in content
                 if isinstance(item, dict) and item.get("type") == "text"]
        return " ".join(parts)
    return str(content)


def llm_extraction_node(state: LlmInput, config: RunnableConfig, runtime: Runtime[Context]) -> LlmOutput:
    """
    title: 大模型分类摘要与质检
    desc: 调用大模型输出严格的JSON文本，完成问题分类、摘要与R01/R02/R03三项质检。
    integrations: 大语言模型
    """
    try:
        cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config["metadata"]["llm_cfg"])
        with open(cfg_file, "r", encoding="utf-8") as fd:
            cfg = json.load(fd)
        llm_config = cfg.get("config", {})
        sp = cfg.get("sp", "")
        up = cfg.get("up", "")

        messages_in: List[Dict[str, Any]] = state.messages or []
        rules_in: List[Dict[str, Any]] = state.rules or []

        up_tpl = Template(up)
        user_prompt = up_tpl.render({
            "ticket_id": state.ticket_id or "",
            "messages": messages_in,
            "rules": rules_in,
        })

        client = LLMClient(config=Config(), ctx=runtime.context)
        response = client.invoke(
            messages=[
                SystemMessage(content=sp),
                HumanMessage(content=user_prompt),
            ],
            model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
            temperature=llm_config.get("temperature", 0.1),
            top_p=llm_config.get("top_p", 1.0),
            max_completion_tokens=llm_config.get("max_completion_tokens", 4000),
            thinking=llm_config.get("thinking", "disabled"),
        )
        raw = _safe_text(getattr(response, "content", "")).strip()
        return LlmOutput(llm_raw=raw, llm_ok=True)
    except Exception as e:
        return LlmOutput(llm_raw="", llm_ok=False)