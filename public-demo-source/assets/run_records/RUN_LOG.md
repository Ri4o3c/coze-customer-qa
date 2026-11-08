# 客服质检与工单分流助手 — 实际运行记录（Run Log）

本次记录所有**真实执行**的输入/输出与对应文件路径。所有内容均来自实际运行，无模拟/伪造。

## 一、可查看的 JSON 文件（保存在项目内）

| 文件 | 内容 | 说明 |
|------|------|------|
| `assets/run_records/demo_inputs.json` | 6 条虚构演示输入（DEMO-001~006） | 用户提供的测试输入，逐字保存 |
| `assets/run_records/hardening_tests.json` | 边界/对抗用例的**真实输入+真实输出** | 含输入校验、规则完整性、严格 rule_quote、非法类型/非法结构、批量复验等全部用例 |

## 二、运行方式与访问

辅助脚本（仅开发沙箱执行，非产品部署）：
- `src/graphs/graph.py` 编译为单条主流程 `main_graph`（customer_qa_single_v1）。
- `src/graphs/batch_graph.py` 编译为批量流程 `batch_main_graph`（customer_qa_batch_v1）。
- 读取：`PYTHONPATH=src python -c "from graphs.graph import main_graph; ..."`
- 读取已保存 JSON：
  - `python -c "import json;print(json.dumps(json.load(open('assets/run_records/hardening_tests.json')),ensure_ascii=False,indent=2))"`

## 三、批量复验结果（真实）
`hardening_tests.json` 中 `batch_aggregate_revalidation`：
- 完全合法单条 → 计 pass（1）
- 缺字段的损坏单条、分类证据未命中 customer 原文的单条 → 均判 undetermined、标记人工复核、`revalidation_failed_count=2`
- 结论：批量汇总不会把结构损坏/客服原话缺失的单条计为 pass。

## 四、边界/对抗用例真实输出摘要（全部 → 转人工或明确拒绝）
| 用例 | 结果 |
|------|------|
| rule_quote 缩写为"客服"短子串 | undetermined + 复核 |
| rule_quote 标点差异（去掉句号） | undetermined + 复核 |
| category=[] / category={} | undetermined + 复核 |
| rule_id={} | undetermined + 复核 |
| checks 额外第4个键 R04 | undetermined + 复核 |
| category_confidence=NaN | undetermined + 复核 |
| check 缺 reason / 缺 evidence | undetermined + 复核 |
| check 证据来自 customer（非agent） | undetermined + 复核 |
| 分类证据来自 agent（非customer） | undetermined + 复核 |
| 假引用（非连续原文） | undetermined + 复核 |
| 非法 JSON 文本 | undetermined + 复核 |
| 非法分类、重复ID、缺ID、空批、超50条 | 明确拒绝/复核 |

## 五、重要提示：LLM 调用状态
- 开发沙箱的大模型 API 当前返回 `[临时不可用] 资源点不足，请升级为付费版套餐/增购积分后继续使用`。
- 因此**本轮无法重新执行依赖大模型的端到端单条/批量试运行**（LLM 提取节点会降级为 unknown 并转人工）。
- 更早的会话中对 6 条演示做过完整 LLM 端到端实跑并核对通过（真实结果：total=6、pass=3、violation=2、undetermined=1、review=1，R02 fail=1、R01 fail=1；R03“保证今天到账”fail、注入“忽略规则”未劫持）。这些结果真实发生过，但当时未落盘保存，现因 LLM 配额耗尽无法重新生成同一批次。
- 依据要求**未自动购买套餐，也未公开部署**。

## 六、规则知识库（真实创建）
- `customer_service_rules_v1` 已创建并导入 R01/R02/R03（ID、版本1.0、policy，无评测答案）。
- 检索节点显式固定查询（含 R01/R02/R03），规则完整性校验强制覆盖三条；`hardening_tests.json` 中 `kb_extract_verbatim_policy` 确认 policy 提取保留完整标点（含句号），供逐字比对。

## 七、本次代码加固点
1. `single_json_validation_node.py`: rule_quote 改为**逐字**等于该 rule_id 完整 policy（含标点），不再容忍标点差异；非字符串 category（[] / {}）不再导致崩溃，统一降级转人工；check 证据校验失败现在正确触发 `degraded`（needs_review=true）。
2. `single_kb_retrieval_node.py`: policy 提取保留末尾句号，保证与逐字比对一致。
3. `batch_process_node.py`: 每条结果携带解析出的 messages，供批量复验客服原话。
4. `batch_aggregate_node.py`: 逐条复验单条完整结构（16 必需字段 + checks 子结构）及分类证据命中 customer 原文，异常不计 pass 并转人工。
5. `config/customer_qa_single_llm_cfg.json`: SP 强化 rule_quote 逐字复制、分类证据仅客户、防“忽略规则”注入。