# Coze 客服质检与工单分流助手

面向虚构电商售后对话，按“分类—规则检索—证据核对—人工复核”组织单条与批量质检。识别五类问题，检查 R01/R02/R03 三条规则；输出 JSON、中文报告与复核建议，不直接退款或创建工单。

## 完整源码入口

| 目录 | 内容 |
| --- | --- |
| `public-demo-source/` | FastAPI 同源网页及 LangGraph 单条/批量流程、配置、脚本、依赖锁和历史验证材料 |
| `workflow-source/` | Coze 工作流项目导出源码与配置、验证入口 |
| `learning-materials/` | 传统七节点材料、规则知识库、提示词、样例及本地测试 |
| `evidence/` | 已保存的历史验收与软件复验记录 |

两套导出源码分别保留，避免将平台 Graph 实现与传统低代码节点材料混为一个运行入口。

## AI工具协作

通过 Grok Bot 调用 Codex 编排任务。本人负责分类、质检、证据与复核规则，以及阶段反馈和验收要求；Codex 辅助工作流、JSON 契约、单条/批量网页实现与异常调试，并协助校验缺规则、无效 JSON、证据角色混淆及批量漏项等边界。

## 运行与验收

节点材料的本地测试入口：

```bash
python -m unittest discover -s learning-materials/tests -v
```

公开演示网页入口 `public-demo-source/src/demo_page.py`，API 入口 `src/demo_api.py`；单条 Graph 入口 `src/graphs/graph.py` 的 `main_graph`，批量入口 `src/graphs/batch_graph.py` 的 `batch_main_graph`。

完整 Graph 需要 Coze Cloud SDK、自己的凭据及规则知识库。按各子目录 README 配置，不承诺 Windows 上直接安装整个云端依赖即可运行。真实模型调用需显式配置并可能产生费用。

历史复验记录：44 项节点材料测试、34 项 Graph 确定性边界检查通过。对应日志位于 `evidence/`，不等于整体模型准确率；历史模型输入/输出位于各项目的 `verification/`。本次公开源码未重新调用线上模型或部署服务。

![完整页面展示](docs/screenshots/coze-review.png)

截图使用原项目页面与历史 R03 样例结果回放，不能视作本次线上模型实测。历史公开演示链接也不保证当前持续可用。

## 发布范围

已保留源码、依赖声明与锁、规则/提示词、样例、测试、历史验证和运行文档；账户绑定 `.coze` 元数据、凭证、缓存及运行环境未上传。此仓库是源码归档，不是经过官方导入验证的工作流 DSL。完整文件清单见 [PUBLICATION.md](PUBLICATION.md)。
