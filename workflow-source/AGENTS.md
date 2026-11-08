## 项目概述
- **名称**: 客服质检与工单分流助手
- **功能**: 对虚构电商售后客服对话进行复核（五类问题分流），依据规则库 R01/R02/R03 进行逐规则质检，输出分类、摘要、质检状态、中文报告与复核建议；支持单条与批量两条流程。

### 节点清单（单条主流程 customer_qa_single_v1，位于 `src/graphs/graph.py`，编译变量 `main_graph`）
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| validate | `nodes/single_validate_node.py` | task | 解析并校验 record_json：ID非空、角色仅customer/agent、两种角色均存在、2-100条、全文≤20000字符 | route_valid: 有效→kb_retrieval, 无效→finalize(人工) | - |
| kb_retrieval | `nodes/single_kb_retrieval_node.py` | task | 显式检索规则库，固定查询含R01/R02/R03，强制检索三条(不依赖模型选择) | - | - |
| rule_check | `nodes/single_rule_check_node.py` | task | 规则完整性校验：必须覆盖R01/R02/R03、版本1.0、无同ID冲突；缺一或冲突→人工，不凭常识补齐 | route_rules: 通过→llm_extraction, 缺→finalize(人工) | - |
| llm_extraction | `nodes/single_llm_extraction_node.py` | agent | 大模型提取分类、置信度、摘要、R01/R02/R03三项质检、needs_review | - | `config/customer_qa_single_llm_cfg.json` |
| json_validation | `nodes/single_json_validation_node.py` | task | 代码校验JSON字段/证据引用/规则引用：rule_quote须逐字等于该rule_id完整policy原文（含标点，不接受缩写/标点差异子串）、category须为字符串且属于五类、分类证据仅来自customer、质检证据仅来自agent；角色混淆/假引用/漏字段/重复规则/非字符串category/NaN置信度/无效JSON任一异常→整条降级unknown并转人工 | route_review: review→finalize, normal→finalize | - |
| finalize | `nodes/single_finalize_node.py` | task | 组装 result_json、中文 report、needs_review；计算 qc_status、route 路由 | - | - |

**类型说明**: task(task节点) / agent(大模型) / condition(条件分支)

### 节点清单（批量流程 customer_qa_batch_v1，位于 `src/graphs/batch_graph.py`，编译变量 `batch_main_graph`）
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 |
|-------|---------|------|---------|---------|
| batch_parse | `nodes/batch_parse_node.py` | task | 解析 records_json 数组(1-50条)，校验ID非空且唯一；缺ID或重复ID整批拒绝 | route_batch: 通过→batch_process, 拒绝→batch_aggregate |
| batch_process | `nodes/batch_process_node.py` | task | 复用单条 `main_graph` 批处理，并发2、次数上限50；按ticket_id关联，漏项补unknown、重复标复核、未知ID记批次错误不重复计数 | - |
| batch_aggregate | `nodes/batch_aggregate_node.py` | task | 聚合统计(total/pass/violation/undetermined/review/category_counts/rule_violation_counts/review_records/逐条results)及中文报告；逐条复验单条完整结构(16必需字段+checks子结构)及分类证据须命中customer原文，复验异常不计pass并标记转人工 | - |

## 子图清单
| 子图名 | 文件位置 | 功能描述 | 被调用节点 |
|-------|---------|------|---------|
| customer_qa_single_v1 (main_graph) | `graphs/graph.py` | 单条质检主流程 | batch_process（在批量流程中复用） |

## 规则知识库
- **名称**: customer_service_rules_v1（虚构规则，仅R01/R02/R03，版本1.0，禁止加入评测预期答案）
- **R01**: 客服不得辱骂、嘲讽或贬低客户。
- **R02**: 客服不得索取客户的账户密码、支付密码或支付验证码。
- **R03**: 退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点。
- **检索方式**: 由 `kb_retrieval` 节点显式检索（固定查询同时含R01/R02/R03），并通过 `rule_check` 强制校验完整覆盖。

## 技能使用
- `llm_extraction` 使用「大语言模型」技能（doubao-seed-2-0-pro-260215）。
- `kb_retrieval` 使用「知识库」技能（创建/语义检索 customer_service_rules_v1）。

## 运行与验证入口(scripts)
- `scripts/run_demo.py`：单条/批量/反例回归入口。子命令 `all|batch|single <r03|injection|DEMO-xxx>|single --record-json '{...}'|hardening`。
  - 单条=调用 `main_graph`；批量=调用 `batch_main_graph`（内部复用单条，并发2、上限50）。
  - 框架 flow 预览仅暴露单条 `main_graph`，批量无独立画布预览入口（见 README）。
- `scripts/run_hardening_tests.py`：确定性边界测试驱动（不依赖大模型），覆盖 rule_quote 逐字比对、非法类型/NaN/缺字段/非法route、customer/agent 证据分开校验、规则完整性缺失/冲突、批量解析与批量复验。

## 验证产物(verification/)
- `verification/overview.json`、`batch_demo6.json`、`single_r03.json`、`single_injection.json`、`hardening_result.json`、`README.md`
- 含真实输入、原始输出、模型、运行时间、源码版本(git commit)，不含密钥。详见 `verification/README.md`。