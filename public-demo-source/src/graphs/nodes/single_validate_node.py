import json
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ValidateInput, ValidateOutput

MAX_MESSAGES = 100
MIN_MESSAGES = 2
MAX_TOTAL_CHARS = 20000
ALLOWED_ROLES = {"customer", "agent"}


def _normalize_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def validate_node(state: ValidateInput, config: RunnableConfig, runtime: Runtime[Context]) -> ValidateOutput:
    """
    title: 输入校验
    desc: 解析record_json并校验记录ID非空、消息角色仅customer/agent、两种角色均存在、2至100条消息、全文不超过20000字符；超限不截断，直接转人工复核。
    """
    ticket_id: str = ""
    messages: List[Dict[str, Any]] = []
    valid: bool = True
    err: str = ""

    raw: str = _normalize_str(state.record_json).strip()
    if not raw:
        return ValidateOutput(validation_valid=False, validation_error="record_json为空",
                              ticket_id="", messages=[])

    try:
        obj = json.loads(raw)
    except Exception as e:
        return ValidateOutput(validation_valid=False, validation_error=f"record_json不是合法JSON: {e}",
                              ticket_id="", messages=[])

    if not isinstance(obj, dict):
        return ValidateOutput(validation_valid=False, validation_error="record_json必须是JSON对象",
                              ticket_id="", messages=[])

    ticket_id = _normalize_str(obj.get("ticket_id", "")).strip()
    if not ticket_id:
        return ValidateOutput(validation_valid=False, validation_error="ticket_id不能为空",
                              ticket_id="", messages=[])

    msgs_raw = obj.get("messages", [])
    if not isinstance(msgs_raw, list):
        return ValidateOutput(validation_valid=False, validation_error="messages必须是数组",
                              ticket_id=ticket_id, messages=[])
    if not (MIN_MESSAGES <= len(msgs_raw) <= MAX_MESSAGES):
        return ValidateOutput(validation_valid=False,
                              validation_error=f"消息条数必须为{MIN_MESSAGES}至{MAX_MESSAGES}条，实际{len(msgs_raw)}条",
                              ticket_id=ticket_id, messages=[])

    roles_seen = set()
    total_chars = 0
    for i, m in enumerate(msgs_raw):
        if not isinstance(m, dict):
            return ValidateOutput(validation_valid=False,
                                  validation_error=f"第{i}条消息必须是JSON对象", ticket_id=ticket_id, messages=[])
        role = _normalize_str(m.get("role", "")).strip()
        text = _normalize_str(m.get("text", ""))
        if role not in ALLOWED_ROLES:
            return ValidateOutput(validation_valid=False,
                                  validation_error=f"第{i}条消息角色不合法: {role}（仅允许customer/agent）",
                                  ticket_id=ticket_id, messages=[])
        total_chars += len(text)
        roles_seen.add(role)
        messages.append({"role": role, "text": text})

    if "customer" not in roles_seen or "agent" not in roles_seen:
        return ValidateOutput(validation_valid=False,
                              validation_error="对话必须同时包含customer与agent两种角色",
                              ticket_id=ticket_id, messages=[])
    if total_chars > MAX_TOTAL_CHARS:
        # 超限不截断，直接转人工复核
        return ValidateOutput(validation_valid=False,
                              validation_error=f"对话全文合计{total_chars}字符超过{MAX_TOTAL_CHARS}上限，不截断，转人工复核",
                              ticket_id=ticket_id, messages=[])

    return ValidateOutput(validation_valid=valid, validation_error=err,
                          ticket_id=ticket_id, messages=messages)