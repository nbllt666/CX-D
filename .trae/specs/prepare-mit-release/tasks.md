# Tasks

- [x] Task 1: 添加 MIT 许可证与项目元数据
  - [x] SubTask 1.1: 在仓库根目录新增标准 MIT `LICENSE`，版权行为 `Copyright (c) 2026 CX-Project`
  - [x] SubTask 1.2: 在 `pyproject.toml` 声明 MIT 许可证，并与构建后端版本兼容
  - [x] SubTask 1.3: 在 README 末尾添加许可证小节

- [x] Task 2: 整理对外卖点
  - [x] SubTask 2.1: 在 README 开头新增「为什么是 CX-D」卖点章节，覆盖双 LLM 共演、三模式、上下文隔离、离线 Mock、Docker vLLM、零构建界面、可移植性
  - [x] SubTask 2.2: 校对卖点与后文说明/命令一一对应，删除无法验证的表述

- [x] Task 3: 执行自动化回归并修复问题
  - [x] SubTask 3.1: 运行 `pytest`，确认全量通过
  - [x] SubTask 3.2: 若失败或缺失覆盖，修复实现或补充测试后重跑

- [x] Task 4: Mock 模式 API 与 Web 全流程验收
  - [x] SubTask 4.1: 以 Mock 模式启动服务，验证 health、四种模式入睡、插话/继续、醒来、recall、会话列表与档案
  - [x] SubTask 4.2: 在浏览器完成入睡、多回合、插话、醒来、查看档案与历史
  - [x] SubTask 4.3: 验证 `dreamless` 不发起 LLM 请求

- [x] Task 5: 真实 Docker vLLM 端到端验收
  - [x] SubTask 5.1: 启动 Docker Desktop 与 CX-O vLLM 容器，确认 `http://127.0.0.1:8080/v1/models` 返回模型
  - [x] SubTask 5.2: 以 `DREAMTALK_BASE_URL=http://127.0.0.1:8080/v1`、`DREAMTALK_MODEL=auto` 启动 DreamTalk，确认 `mock=false`
  - [x] SubTask 5.3: 创建并完成一场真实模型梦境，验证导演/梦者文本非 Mock 文案、醒来摘要正常，容器日志可见请求

  > 环境说明（2026-11-22）：CX-O compose 默认模型 `C:\CX-O\models\model.gguf` 不存在，未启动该容器；实际启动并验收的是 8080 上既有的 `duplex-vllm`（vLLM v0.22.0，gemma-4-e4b-it，served-model-name=`model.gguf`）。DreamTalk 的 Docker vLLM 接入链路与验收目标一致。

- [x] Task 6: 发布卫生与最终核对
  - [x] SubTask 6.1: 确认 `.env`、`data/`、`.screenshots/`、缓存未进入版本库，`git status` 只含预期文件
  - [x] SubTask 6.2: 核对 LICENSE、README、`pyproject.toml` 许可证信息一致
  - [x] SubTask 6.3: 汇总验收结果与已知限制（如 Docker / 模型前置条件）

# Task Dependencies

- Task 4 depends on Task 3
- Task 5 depends on Task 3
- Task 6 depends on Task 1, Task 4, Task 5
- Task 2 可与 Task 1 并行
