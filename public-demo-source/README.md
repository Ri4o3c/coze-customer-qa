# 客服质检与工单分流助手

虚构电商售后客服对话复核与工单分流工作流，含两条流程：

- **单条流程 `customer_qa_single_v1`**：`src/graphs/graph.py` 编译的 `main_graph`。
  输入 `record_json`（JSON 对象字符串），经 输入校验 → 选择器(人工兜底) → 知识库检索 →
  规则完整性校验 → 选择器(缺规则人工) → 大模型提取 → 代码校验JSON/证据/规则 →
  复核分支选择器 → 结果与中文报告。输出 `result_json` / `report` / `needs_review`。
- **批量流程 `customer_qa_batch_v1`**：`src/graphs/batch_graph.py` 编译的 `batch_main_graph`。
  输入 `records_json`（单条记录数组字符串，1–50 条，ID 非空且唯一），批处理节点**复用单条流程**
  （逐条绑定 `item.record_json`，并发 2、次数上限 50），按 `ticket_id` 关联，输出 `summary_json` / `report`。

规则知识库：`customer_service_rules_v1`（客户侧已创建，仅 R01/R02/R03 三条虚构规则，每条含 ID、版本 1.0、policy）。

## 运行方式（在项目根目录执行）

### 单条流程（框架预览仅支持单条）
```bash
bash scripts/local_run.sh -m flow -i '{"record_json":"{\"ticket_id\":\"DEMO-002\",\"messages\":[{\"role\":\"customer\",\"text\":\"我想申请退货退款。\"},{\"role\":\"agent\",\"text\":\"把支付验证码发给我，我帮你办退款。\"}]}"}'
# 或直接调用单条图：
PYTHONPATH=src python scripts/run_demo.py single --record-json '{...}'
```

### 批量流程（框架 flow 预览无批量，脚本或网页批量页进入）
> ⚠️ 说明：框架 flow 预览只暴露单条 `main_graph`，批量**没有独立的画布预览入口**，请通过脚本（或下方的公开演示网页批量页）进入批量流程。
```bash
PYTHONPATH=src python scripts/run_demo.py batch          # 运行6条演示批量
PYTHONPATH=src python scripts/run_demo.py all            # 批量6条 + R03反例 + 注入反例 + 确定性边界
PYTHONPATH=src python scripts/run_demo.py hardening      # 确定性边界（不依赖大模型）
```

所有运行结果（真实输入、原始输出、模型、时间、源码版本）一并写入 `verification/`，详见 [`verification/README.md`](verification/README.md)。

## 公开演示网页（FastAPI 同源，免登录）
在既有 FastAPI 服务（`src/main.py` 的 `app`）上注册，根路径为演示页，模型与规则知识库均在**服务端**调用，密钥不回传前端、不保存用户原始对话，模型文本以纯文本渲染。

启动（部署端口取 `DEPLOY_RUN_PORT`，默认 5000）：
```bash
bash scripts/http_run.sh                      # = python src/main.py -m http -p $PORT
# 本地稳定验证（关闭 reload）：
PYTHONPATH=src python -m uvicorn main:app --host 0.0.0.0 --port 5077
```

| 路由 | 说明 |
|---|---|
| `GET /` | 演示页：单条分析 + 批量分析（手机可用、示例一键填充、下载 JSON） |
| `POST /api/demo/single` | body `{ticket_id,messages}` 或 `{record_json}`，复用单条 `main_graph` |
| `POST /api/demo/batch` | body `{records:[…]}` 或 `{records_json}`，复用批量 `batch_main_graph`（1–50 条） |
| `GET /api/demo/health` | 健康检查 |

> 部署说明：代码已就绪并完成本地启动+端到端验证（1 条真实 R02、批量 6 条）。**批量网页存在，含批量页**；框架画布 flow 预览仍仅单条。是否对外公开由你点击平台部署，本仓库不自动购买套餐、不主动公开部署。

## 质检与分流规则
- 五类问题 → 去向：物流配送→物流客服；退款退货→售后客服；商品质量→商品售后；订单与支付→订单客服；其他→综合客服。
- `category_confidence`<0.75 或模型声明需复核 → 转人工；多诉求无法确定主次 → 转人工。
- `rule_quote` 逐字等于完整 policy；分类证据仅 customer 原文、质检证据仅 agent 原文，分开校验；任一 fail→violation、
  有 unknown→undetermined、全 pass→pass；复核为独立维度。
- 仅产建议（`action=suggest_only`），**不实际建单、退款或发送任何消息**；仓库不自动购买套餐。

## 目录速览
- `src/graphs/graph.py`：单条主流程 + 选择器
- `src/graphs/batch_graph.py`：批量流程
- `src/graphs/nodes/`：各节点实现
- `src/graphs/state.py`：全局状态 + 各节点出入参
- `config/customer_qa_single_llm_cfg.json`：大模型配置（当前 `doubao-seed-2-0-pro-260215`）
- `scripts/run_demo.py` / `scripts/run_hardening_tests.py`：回归运行入口
- `verification/`：真实试运行记录