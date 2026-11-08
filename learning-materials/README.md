# Coze 低代码客服质检与工单分流助手 v1

场景：虚构电商售后。目标是复核已经发生的客服对话，提供分类、规则质检、原文证据和分流建议。

线上项目：[客服质检工作流](https://code.coze.cn/p/7700153860433969202)。已经创建在当前用户账号的扣子编程中。请先读 `docs/06_线上项目使用.md`，无需从头照文档重建。

## 当前交付状态

- 已提供：3份可上传规则、完整模型提示词、7份可粘贴Python节点代码、单条/批量连接说明、评测样例、输入文件、自动化测试。
- 本地软件测试结果见 `verification/验证记录.md`，仅证明节点代码处理相应夹具的行为。
- 已在Coze创建开发项目、规则知识库与两条工作流实现；充值后加固版完成6条批量与2个反例的真实模型回归，平台34项确定性边界测试通过，最终保存版本62c3e0f。另有最终画布R02独立运行记录，详见验证记录。
- 线上采用当前“扣子编程”的Python Graph可视化工作流；本文件夹nodes目录是传统低代码画布的独立节点材料，接口不同，不能直接覆盖线上Graph节点。
- 本文件夹和ZIP是项目材料包，不是经过Coze导入验证的工作流导出包。不要把ZIP上传到“导入工作流”入口。
- 没有生产准确率、知识库召回率或已上线的声明；30条评测样例尚未全部用实际模型执行。

## 传统低代码节点材料的使用方式

以下用于学习或在旧版低代码画布复现；已创建的线上项目使用方式见docs/06。

1. 按 `docs/01_单条工作流搭建.md` 创建 `customer_qa_single_v1`。
2. 上传 `knowledge/` 内3份TXT到同一个专用文本知识库。只上传这3份，不上传提示词、测试题、预期答案或简历。
3. 粘贴 `prompts/` 与 `nodes/` 内容，按端口连接表配置变量。代码语言选择Python。
4. 用 `data/single_normal.json` 和 `data/single_violation.json` 试运行；对照人工预期，再测试 `single_review.json`。
5. 单条通过验收并发布后，按 `docs/02_批量工作流搭建.md` 创建 `customer_qa_batch_v1`。
6. 用 `data/batch_demo.json` 运行批量，按 `docs/03_验收与演示.md` 检查。

当前Coze界面入口可能因账号版本不同而改变。请进入低代码工作流画布，而不是让首页通用聊天助手临时分析一段对话。官方说明见 `docs/04_官方来源.md`。

## 输入约定

单条开始节点只有一个String输入 `record_json`。其内容是一个JSON对象文本：

```json
{
  "ticket_id": "DEMO-001",
  "messages": [
    {"role":"customer","text":"我的包裹三天没更新了。"},
    {"role":"agent","text":"您好，我帮您联系物流核实。"}
  ]
}
```

在Coze的String输入框，粘贴对象原文即可；若用API调用，外层参数需要JSON转义：`{"record_json":"{\"ticket_id\":...}"}`。本包提供可直接粘贴的开始参数文件，见 `data/*_start_params.json`。

批量开始节点只有一个String输入 `records_json`，内容是多个上述对象组成的JSON数组文本。输入列表须有1至50条、ID非空且唯一。重复ID或缺ID拒绝整批，避免结果错配。对话内容异常但ID有效的行保留，交由单条流程转人工。

单条最多100条消息、合计20000字符。超限拒绝并复核，不静默截断。字符不是token，不保证填满上限时任意模型都能处理；选用足够上下文窗口并根据在线试运行调整上限。

## 输出约定

- 单条：`result_json`（String）、`report`（String）、`needs_review`（Boolean）。
- 批量：`summary_json`（String）、`report`（String）。
- `qc_status`为`pass / violation / undetermined`：当前输入未见违规、发现违规、无法判断。
- `needs_review`是另一独立维度，例如“已发现R01违规，但R03仍无法判断”可同时为violation和true。
- `route`是实际建议去向；待复核统一是“人工复核队列”。`suggested_route`保留已知业务建议。
- 本项目不会建单或实际转接。`ticket_id`只是输入记录标识。
- `validation=code_checked`只表示字段和引用检查通过。`semantic_review`明确保留模型判断尚未人工验证的状态。

## 本地验证

在此文件夹打开终端，使用Python3.11及以上，无第三方依赖：

```powershell
python -m unittest discover -s tests -v
python tools/replay_fixture.py
```

第二个命令将手工构造的模型候选输出送进真实节点，打印演示报告；它不请求大模型，不访问Coze，不是线上运行证明。

## 文件清单

| 目录 | 用途 |
|---|---|
| knowledge | 只含3项自定义业务规则，可上传 |
| prompts | 模型系统/用户提示词 |
| nodes | 7个Python代码节点，每份文件独立粘贴 |
| data | 单条/批量输入、评测输入、人工预期和观察记录模板 |
| schemas | 代码最终输出的JSON Schema与节点端口清单 |
| docs | 单条、批量、异常分支、验收与官方来源 |
| tests | 本地代码边界测试 |
| tools | 手工夹具回放与实际结果评分工具 |
| verification | 真实软件验证记录，不含虚构在线成绩 |

## 尚待平台验收的关键点

知识库输出的内容字段映射、模型实际JSON表现、异常分支是否到达复核结果、批处理子流程结果数组绑定、最终模型质量。平台连接恢复后仍必须完成这些检查。
