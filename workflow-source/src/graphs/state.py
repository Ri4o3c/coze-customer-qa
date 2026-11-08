from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# =====================================================================
# 全局状态 GlobalState（各节点输出会按字段合并到其中）
# =====================================================================
class GlobalState(BaseModel):
    """工作流全局过程状态"""
    ticket_id: str = Field(default="", description="记录ID")
    validation_valid: bool = Field(default=False, description="输入校验是否通过")
    validation_error: str = Field(default="", description="输入校验错误信息")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="规范化后的消息列表[{role,text}]")
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="检索到的规则列表")
    rules_ok: bool = Field(default=False, description="规则完整性校验是否通过")
    rules_reason: str = Field(default="", description="规则校验说明")
    llm_raw: str = Field(default="", description="大模型返回原文")
    llm_ok: bool = Field(default=False, description="大模型调用是否成功")
    category: str = Field(default="", description="问题分类")
    category_valid: bool = Field(default=False, description="分类是否有效（属于五类之一）")
    category_confidence: float = Field(default=0.0, description="分类置信度(0-1)")
    category_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="分类证据")
    summary: str = Field(default="", description="对话摘要")
    checks: Dict[str, Any] = Field(default_factory=dict, description="R01/R02/R03质检结果")
    needs_review: bool = Field(default=False, description="是否需要人工复核")
    review_reasons: List[str] = Field(default_factory=list, description="复核原因列表")
    qc_status: str = Field(default="undetermined", description="质检状态: pass/violation/undetermined")
    route: str = Field(default="", description="最终去向")
    suggested_route: str = Field(default="", description="建议去向")
    validation: Dict[str, Any] = Field(default_factory=dict, description="校验详情")
    semantic_review: Dict[str, Any] = Field(default_factory=dict, description="语义复核标记")
    result_json: str = Field(default="", description="最终结果JSON字符串")
    report: str = Field(default="", description="中文质检报告")
    batch_flag: str = Field(default="", description="批次标记(内部使用)")

    def model_dump_flat(self) -> Dict[str, Any]:
        """返回可序列化的 dict（供节点返回时使用）"""
        return self.model_dump()


# =====================================================================
# 工作流输入/输出
# =====================================================================
class GraphInput(BaseModel):
    """单条客服质检工作流输入"""
    record_json: str = Field(..., description="内容为JSON对象的字符串，结构{\"ticket_id\":\"...\",\"messages\":[{\"role\":\"customer|agent\",\"text\":\"...\"}]}")


class GraphOutput(BaseModel):
    """单条客服质检工作流输出"""
    result_json: str = Field(..., description="结果JSON字符串")
    report: str = Field(..., description="中文质检报告")
    needs_review: bool = Field(..., description="是否需要人工复核")


# =====================================================================
# 节点1：输入校验
# =====================================================================
class ValidateInput(BaseModel):
    """输入校验节点入参"""
    record_json: str = Field(..., description="原始记录JSON字符串")


class ValidateOutput(BaseModel):
    """输入校验节点出参"""
    validation_valid: bool = Field(..., description="校验是否通过")
    validation_error: str = Field(..., description="校验错误信息(为空表示通过)")
    ticket_id: str = Field(..., description="记录ID")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="规范化消息列表")


# =====================================================================
# 节点2：知识库检索
# =====================================================================
class KbRetrievalInput(BaseModel):
    """知识库检索节点入参（固定查询，无需入参字段）"""
    pass


class KbRetrievalOutput(BaseModel):
    """知识库检索节点出参"""
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="检索到的规则列表")
    retrieval_error: str = Field(default="", description="检索异常信息(为空表示成功)")


# =====================================================================
# 节点3：规则完整性校验
# =====================================================================
class RuleCheckInput(BaseModel):
    """规则完整性校验节点入参"""
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="检索到的规则列表")


class RuleCheckOutput(BaseModel):
    """规则完整性校验节点出参"""
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="规范化后的规则列表")
    rules_ok: bool = Field(..., description="完整性校验是否通过(必须完整覆盖R01/R02/R03且无同ID冲突)")
    rules_reason: str = Field(..., description="校验说明")


# =====================================================================
# 节点4：大模型提取
# =====================================================================
class LlmInput(BaseModel):
    """大模型提取节点入参"""
    ticket_id: str = Field(..., description="记录ID")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="消息列表")
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="规则列表")


class LlmOutput(BaseModel):
    """大模型提取节点出参"""
    llm_raw: str = Field(default="", description="模型返回原文(JSON字符串)")
    llm_ok: bool = Field(..., description="模型调用是否成功")


# =====================================================================
# 节点5：代码校验JSON/证据/规则
# =====================================================================
class JsonValidationInput(BaseModel):
    """代码校验节点入参"""
    ticket_id: str = Field(..., description="记录ID")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="消息列表")
    llm_raw: str = Field(default="", description="模型返回原文")
    llm_ok: bool = Field(..., description="模型调用是否成功")
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="规则列表")


class JsonValidationOutput(BaseModel):
    """代码校验节点出参"""
    category: str = Field(default="", description="问题分类")
    category_valid: bool = Field(default=False, description="分类是否有效")
    category_confidence: float = Field(default=0.0, description="分类置信度")
    category_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="分类证据")
    summary: str = Field(default="", description="摘要")
    checks: Dict[str, Any] = Field(default_factory=dict, description="质检结果")
    needs_review: bool = Field(default=False, description="是否需要人工复核")
    review_reasons: List[str] = Field(default_factory=list, description="复核原因")
    qc_status: str = Field(default="undetermined", description="质检状态")
    validation: Dict[str, Any] = Field(default_factory=dict, description="校验详情")
    semantic_review: Dict[str, Any] = Field(default_factory=dict, description="语义复核标记")


# =====================================================================
# 节点6：结果与中文报告
# =====================================================================
class FinalizeInput(BaseModel):
    """结果整理节点入参"""
    ticket_id: str = Field(default="", description="记录ID")
    validation_valid: bool = Field(default=False, description="输入校验是否通过")
    validation_error: str = Field(default="", description="输入校验错误")
    rules_ok: bool = Field(default=False, description="规则完整性是否通过")
    rules_reason: str = Field(default="", description="规则校验说明")
    category: str = Field(default="", description="问题分类")
    category_valid: bool = Field(default=False, description="分类是否有效")
    category_confidence: float = Field(default=0.0, description="分类置信度")
    category_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="分类证据")
    summary: str = Field(default="", description="摘要")
    checks: Dict[str, Any] = Field(default_factory=dict, description="质检结果")
    needs_review: bool = Field(default=False, description="是否需要人工复核")
    review_reasons: List[str] = Field(default_factory=list, description="复核原因")
    qc_status: str = Field(default="undetermined", description="质检状态")
    validation: Dict[str, Any] = Field(default_factory=dict, description="校验详情")
    semantic_review: Dict[str, Any] = Field(default_factory=dict, description="语义复核标记")


class FinalizeOutput(BaseModel):
    """结果整理节点出参"""
    result_json: str = Field(..., description="结果JSON字符串")
    report: str = Field(..., description="中文质检报告")
    needs_review: bool = Field(..., description="是否需要人工复核")
    ticket_id: str = Field(default="", description="记录ID")
    qc_status: str = Field(default="undetermined", description="质检状态")
    category: str = Field(default="", description="问题分类")


# =====================================================================
# 选择器(条件分支)状态
# =====================================================================
class ValidRouteState(BaseModel):
    """输入校验选择器状态"""
    validation_valid: bool = Field(default=False, description="输入校验是否通过")


class RulesRouteState(BaseModel):
    """规则校验选择器状态"""
    rules_ok: bool = Field(default=False, description="规则完整性是否通过")


class ReviewRouteState(BaseModel):
    """复核选择器状态"""
    needs_review: bool = Field(default=False, description="是否需要人工复核")


# =====================================================================
# 批量流程
# =====================================================================
class BatchInput(BaseModel):
    """批量质检工作流输入"""
    records_json: str = Field(..., description="内容为单条记录数组的JSON字符串(1-50条)")


class BatchOutput(BaseModel):
    """批量质检工作流输出"""
    summary_json: str = Field(..., description="批量汇总JSON字符串")
    report: str = Field(..., description="中文批量汇总报告")


class BatchParseInput(BaseModel):
    """批量解析节点入参"""
    records_json: str = Field(..., description="批量记录JSON字符串")


class BatchParseOutput(BaseModel):
    """批量解析节点出参"""
    parse_ok: bool = Field(..., description="批次是否通过校验(缺ID或重复ID整批拒绝)")
    parse_error: str = Field(..., description="批次校验错误信息")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="待处理项[{ticket_id,record_json}]")
    ticket_ids: List[str] = Field(default_factory=list, description="有效记录ID列表")
    duplicate_ids: List[str] = Field(default_factory=list, description="重复ID列表")


class BatchProcessInput(BaseModel):
    """批处理节点入参"""
    items: List[Dict[str, Any]] = Field(default_factory=list, description="待处理项[{ticket_id,record_json}]")


class BatchProcessOutput(BaseModel):
    """批处理节点出参"""
    results: List[Dict[str, Any]] = Field(default_factory=list, description="逐条处理结果")


class BatchAggregateInput(BaseModel):
    """批量聚合节点入参"""
    results: List[Dict[str, Any]] = Field(default_factory=list, description="逐条处理结果")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="待处理项")


class BatchAggregateOutput(BaseModel):
    """批量聚合节点出参"""
    summary_json: str = Field(..., description="批量汇总JSON字符串")
    report: str = Field(..., description="中文批量汇总报告")


class BatchGlobalState(BaseModel):
    """批量流程全局状态"""
    records_json: str = Field(default="", description="批量记录JSON")
    parse_ok: bool = Field(default=False, description="批次解析校验是否通过")
    parse_error: str = Field(default="", description="批次校验错误")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="待处理项")
    ticket_ids: List[str] = Field(default_factory=list, description="有效ID列表")
    duplicate_ids: List[str] = Field(default_factory=list, description="重复ID列表")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="逐条处理结果")
    summary_json: str = Field(default="", description="批量汇总JSON")
    report: str = Field(default="", description="批量中文汇总报告")


class BatchRouteState(BaseModel):
    """批量流程解析选择器状态"""
    parse_ok: bool = Field(default=False, description="批次解析校验是否通过")