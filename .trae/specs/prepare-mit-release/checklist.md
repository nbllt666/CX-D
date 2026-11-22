# Checklist

- [x] 仓库根目录存在 `LICENSE`，内容为标准 MIT 全文
- [x] `LICENSE` 版权行为 `Copyright (c) 2026 CX-Project`
- [x] `pyproject.toml` 声明 MIT 许可证，构建/安装不因许可证元数据报错
- [x] README 末尾存在许可证小节，与 `LICENSE` 一致
- [x] README 开头存在「为什么是 CX-D」卖点章节
- [x] 卖点覆盖双 LLM 共演、三模式、上下文隔离、离线 Mock、Docker vLLM、零构建界面、可移植性
- [x] 每条卖点都能在后文说明、配置或验收命令中找到依据
- [x] README 原有快速开始、配置项、HTTP API、移植信息未被删除或削弱
- [x] `pytest` 全量通过，无失败、无跳过
- [x] Mock 模式下 `/api/health` 返回 `mock=true`
- [x] Mock 模式下 auto / memory / wild / dreamless 四种入睡方式均可用
- [x] 插话与继续做梦可推进回合，回合数不超过配置上限
- [x] 醒来返回标题、余韵、情绪残留，`/api/recall` 只返回摘要字段
- [x] 会话列表与会话档案可读取，档案包含完整回合
- [x] `dreamless` 模式不产生 LLM 请求，并返回无梦原因
- [x] 浏览器中可完成入睡、多回合、插话、醒来、档案与历史查看
- [x] Docker vLLM 容器启动后 `/v1/models` 可访问
- [x] DreamTalk 连接 Docker vLLM 时 `/api/health` 返回 `mock=false`
- [x] 真实模型梦境中导演与梦者文本不来自 Mock 文案库，容器日志可见请求
- [x] 真实模型梦境可正常醒来并生成摘要
- [x] `.env`、`data/`、`.screenshots/`、缓存未进入版本库
- [x] `git status` 仅包含本次发布准备的预期文件
- [x] 已记录 Docker / 模型等运行前置条件与已知限制

> 已知限制：CX-O compose 默认模型 `C:\CX-O\models\model.gguf` 缺失，本次真实验收使用 8080 上既有的 `duplex-vllm`（gemma-4-e4b-it）；Docker Desktop 需先启动，容器就绪需要数十秒。DreamTalk 在 LLM 不可用时逐回合回退离线文本，容器恢复后自动重试。
