# CX-D 发布前准备（MIT 协议 / 卖点 / 全功能验收）Spec

## Why

CX-D 已具备双 LLM 梦境对话、三种模式与上下文隔离能力，但公开发布前缺少三样东西：明确的开源许可证、面向使用者的核心卖点说明，以及一份包含真实 Docker vLLM 链路的可复现验收结论。

## What Changes

- 新增 MIT `LICENSE`，版权人为 `CX-Project`，年份 2026；`pyproject.toml` 同步许可证元数据。
- README 增加「为什么是 CX-D」卖点章节，并补充许可证小节；保留现有安装、配置、API、移植文档结构。
- 执行发布前全功能验收：pytest 全量、Mock 模式 API 与 Web 全流程、真实 Docker vLLM 端到端；修复验收中暴露的问题（若有）。
- 确认 `.env`、运行数据、截图、缓存等本地资产不进入版本库。

## Impact

- Affected specs: `add-dreamtalk-dual-llm-chat`（既有能力，本次不改变领域契约）。
- Affected code: 新增 `LICENSE`；修改 `README.md`、`pyproject.toml`；若验收发现问题，涉及 `src/dreamtalk/**`、`web/**`、`tests/**`。

## ADDED Requirements

### Requirement: MIT 许可证

项目 SHALL 以 MIT 许可证发布：仓库根目录提供标准 MIT 全文，版权行为 `Copyright (c) 2026 CX-Project`；`pyproject.toml` SHALL 声明 MIT 许可证，且与 `LICENSE` 一致。

#### Scenario: 许可证可被识别
- **WHEN** 查看仓库根目录与 `pyproject.toml`
- **THEN** 能看到完整 MIT 文本和 MIT 元数据，版权人一致为 `CX-Project`

#### Scenario: 发布包带许可证
- **WHEN** 执行构建或安装项目
- **THEN** 许可证信息随包元数据可读取，不会因缺失 `LICENSE` 产生告警

### Requirement: 对外卖点

README SHALL 在开头提供简洁、可验证的核心卖点，且每条卖点都能在现有功能或文档中找到对应依据，不使用无法验证的夸大表述。卖点至少覆盖：

- 梦者 × 潜意识导演双 LLM 即兴共演，无选项、无骰子；
- 记忆梦 / 天马行空 / 一夜无梦三种模式，支持自动决策与手动指定；
- 梦境内外上下文硬隔离，醒来只向梦外交付摘要；
- 无 API Key 也能用确定性 Mock 离线完整体验；
- 兼容任意 OpenAI 风格接口，支持 Docker vLLM 自动发现模型与本地代理绕过；
- 零构建 Web 界面与可移植的 `core/` 分层，便于回装 CX-O。

#### Scenario: 新读者快速理解价值
- **WHEN** 用户只阅读 README 前半部分
- **THEN** 能说清项目是什么、三种模式的区别、与普通文字 RPG/聊天助手的差异，并找到启动方式

#### Scenario: 卖点可核对
- **WHEN** 阅读任一卖点
- **THEN** README 后文或 `docs/PORTING.md` 中存在对应实现说明或验收命令

### Requirement: 全功能可复现验收

发布前 SHALL 完成以下验收，并全部通过：

- 自动化测试：`pytest` 全量通过，无跳过或失败；
- Mock 链路：`/api/health`、入睡（auto / memory / wild / dreamless）、插话与继续、醒来、清醒摘要、会话列表与档案全部可用；
- Web 链路：入睡面板、梦境回合、醒者插话、醒来摘要、梦境档案、历史侧栏可用；
- 真实 Docker vLLM：启动 CX-O 的 vLLM 容器后，`/v1/models` 可访问，DreamTalk 以 `mock=false` 完成至少一场真实模型梦境与醒来摘要，且回复不来自 Mock 文案库；
- 发布卫生：`LICENSE`、README、`pyproject.toml` 三者一致，`.env` 与运行数据未被纳入版本库。

#### Scenario: Mock 全流程
- **WHEN** 不配置任何 API Key 启动 DreamTalk
- **THEN** 可完成一场含多次回合、插话与醒来摘要的梦境，历史与档案可回看

#### Scenario: 真实 Docker LLM
- **WHEN** Docker Desktop 与 CX-O vLLM 容器就绪，`.env` 指向 `http://127.0.0.1:8080/v1`
- **THEN** 创建会话后梦者与导演回合来自真实模型（容器日志可见请求，文本不属于 Mock 文案库），醒来摘要正常返回

#### Scenario: 无梦不调用 LLM
- **WHEN** 手动指定 `dreamless` 模式入睡
- **THEN** 不产生 LLM 请求，仅返回无梦记录与原因

## MODIFIED Requirements

### Requirement: README 结构

README SHALL 保留现有的快速开始、真实 LLM / Docker vLLM 接入、配置项、HTTP API、测试、目录结构与 CX-O 关系，并在开头新增卖点、结尾新增许可证说明；不得因新增内容删除或削弱既有安装与移植信息。

## REMOVED Requirements

无。
