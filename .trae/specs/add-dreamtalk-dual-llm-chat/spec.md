# DreamTalk（梦话）双 LLM 梦境对话项目 Spec

## Why

CX-O 中的梦境引擎（`C:\CX-O\CX-O-SERVER\server\autonomy\dream\`）是一个深度耦合自治循环、记忆库、图谱、昼夜调度与生理传感器的单 LLM「候选生成 → 过滤 → 缓冲 → 固化」管线，只能作为 CX-O 服务的一部分运行。

本次将其拆分到工作目录 `c:\CX-D`，大改为独立可运行项目：梦境不再是后台生成的候选文本，而由 **「梦者」与「潜意识导演」两个 LLM 实时交替共演**，用户可随时以「醒者」身份插话，形成自由度高于文字 RPG 的对话式梦境；由系统**自动决定**当夜进入「记忆梦」「天马行空」还是「一夜无梦」。

同时确立三条硬约束：

1. **保留原引擎的「根据当天记忆生成」模式**：记忆梦以当天/近期记忆碎片为潜在意象，经两个 LLM 变形、凝缩、移置后共演；独立项目中由用户输入当天记忆，回装 CX-O 后由原采集器（边缘记忆 + 孤立实体 + 日记情绪）供给。
2. **梦境内外上下文隔离**：梦中 LLM 只看见「本次入睡时解析出的记忆素材 + 梦内回合」，看不见任何梦外对话、用户档案、其他会话或既往梦境；醒来后，梦外只能拿到**摘要级**的梦（标题 + 余韵 + 情绪残留），不得自动注入原始梦境回合。
3. **可移植回 CX-O**：核心编排不依赖 FastAPI / SQLite / 环境变量，通过端口与适配器分层，并提供移植指南与兼容适配器，后续可整体装回 CX-O 的自治服务。

## What Changes

- 从 `C:\CX-O\CX-O-SERVER\server\autonomy\dream\` 抽取可用资产到 `c:\CX-D`，重写为**无 CX-O 依赖**的独立 Python 项目（FastAPI + 原生静态对话页 + SQLite）。
- **BREAKING**：梦境生成由「单 LLM 批量候选」改为「双 LLM 交替对话」，原 `DreamEngine.run_session` 的候选语义不再保留。
- **BREAKING**：移除 CX-O 专属依赖：`CircadianScheduler`、`SleepSensor`、`physio`、`MemoryManager`、`GraphRepository`、`AutonomyEngine` 后台循环、WebSocket 事件协议、主库固化/审计链路。
- 新增**记忆源端口 `MemorySource`**：
  - 独立项目默认 `ManualMemorySource`：使用用户在「入睡」时提交的当天记忆；
  - 回装 CX-O 时替换为 `CXOMemorySource`：运行原 `collector.py` 的只读采集逻辑（近 7 天边缘记忆 + 图谱孤立实体 + 最近日记情绪），把结果作为本次梦境素材快照。
- 新增三种梦境模式，默认自动判定（也可显式指定）：
  - `memory` 记忆梦（原引擎模式）：以当天/近期记忆碎片为潜在意象，双 LLM 将其变形、拼接、移置为梦境叙事；
  - `wild` 天马行空：在记忆素材之上允许时空跳跃、身份漂移、元叙事，梦境逻辑刻意失稳；
  - `dreamless` 一夜无梦：**不调用任何 LLM**，不产生对话，返回安静的「无梦」记录与判定原因。
- 新增「醒者介入」：用户随时向梦境发话，两条 LLM 必须承接而非给出选项；不设属性、掷骰、菜单等 RPG 机制，行动完全开放。醒者话语属于梦内事件，不是梦外上下文注入。
- 新增**梦境上下文 / 清醒上下文**双域模型与隔离契约：梦中只读本次素材快照与梦内回合；梦外只消费 `DreamRecall`（摘要、标题、模式、情绪残留）。
- 保留并改造原引擎的三项资产：
  - 确定性内容闸门（事实性断言拦截）→ 逐轮校验梦境文本，命中后要求改写一次；
  - 短连接 SQLite 存储模式 → 本项目的会话/回合表；
  - 醒来摘要（`summarizer.py` 思路）→ 会话结束时生成 `DreamRecall`。
- 新增**可移植分层**：`core`（纯领域）、`ports`（协议）、`adapters`（OpenAI/SQLite/Env/CX-O 兼容），并以 `DreamTalkService` 作为可被 CX-O 直接装配的门面。
- 打包：`pyproject.toml`、`python -m dreamtalk` 启动、`.env.example`、中文 README、`docs/PORTING.md`、pytest 测试、Mock LLM 离线可跑。

## Impact

- Affected specs：梦境生成（重写）、梦境模式（新增记忆梦）、记忆源（新增端口）、梦境上下文隔离（新增）、可移植性契约（新增）、梦境会话协议（新增）、Web 对话界面（新增）、项目打包（新增）。
- Affected code：
  - 参考源：`C:\CX-O\CX-O-SERVER\server\autonomy\dream\{collector,config,filter,buffer,summarizer,generator}.py`；`server/api/routers/dream.py`；`APP-Frontend/src/api/clients/dream.ts`
  - 新项目：`c:\CX-D\src\dreamtalk\`、`c:\CX-D\web\`、`c:\CX-D\tests\`、`c:\CX-D\docs\PORTING.md`、`c:\CX-D\pyproject.toml`

## ADDED Requirements

### Requirement: 独立项目与一键启动

系统 SHALL 在 `c:\CX-D` 提供可独立安装、独立运行的 Python 项目，包名 `dreamtalk`：

- `pyproject.toml` 声明依赖 `fastapi`、`uvicorn`、`httpx`、`python-dotenv`，Python `>=3.11`；
- `python -m dreamtalk` 或控制台脚本 `dreamtalk` 启动 Web 服务（默认 `127.0.0.1:8000`）；
- 运行数据写入 `data/dreamtalk.db`（可用 `DREAMTALK_DATA_DIR` 覆盖），目录自动创建；
- 项目不含任何 `from server...` / CX-O 路径依赖。

#### Scenario: 冷启动
- **WHEN** 用户在 `c:\CX-D` 执行 `pip install -e .` 后运行 `python -m dreamtalk`
- **THEN** 服务启动并在 `http://127.0.0.1:8000` 返回对话页
- **AND** `GET /api/health` 返回 `{"status": "ok", "mock": <bool>, "contract_version": "1.0"}`

#### Scenario: 离线 Mock
- **WHEN** 未配置任何 LLM 密钥且未设置 `DREAMTALK_MOCK`
- **THEN** 系统自动降级为 Mock LLM，仍可完整体验一轮梦境对话
- **AND** 健康检查中 `mock=true`

### Requirement: 记忆梦（原引擎模式）

系统 SHALL 提供 `memory` 模式，忠实延续 CX-O 原梦境引擎「根据记忆生成」的定位：

- 素材来源为 `MemoryMaterial` 快照：
  - `day_memories`：当天/近期记忆碎片（独立项目由用户输入；回装 CX-O 时由 `CXOMemorySource` 采集）；
  - `entities`：孤立实体/零散意象（可选）；
  - `emotion`：情绪基调（valence/arousal，独立项目由界面选择，回装时取最近日记情绪）；
- 两个 LLM 必须以这些碎片为**潜在意象**进行移置、凝缩、拼接与变形，不得逐条复述，不得把碎片断言为真实发生的事；
- 记忆梦的模式指令、温度（`director=0.85` / `dreamer=0.9`）与常态叙事节奏为默认档；
- 显式选择 `memory` 但没有任何 `day_memories` 时返回 422；自动模式下无当天记忆时 `memory` 权重直接归零；
- 独立项目默认 `ManualMemorySource`；回装 CX-O 时 `CXOMemorySource` 应复现原采集口径：近 7 天、基线重要性 < 0.5 的边缘记忆（上限 20，最边缘优先）、度数为 1 的图谱孤立节点、最近日记情绪；采集失败降级为空快照，不阻断入睡。

#### Scenario: 记忆入梦
- **WHEN** 用户提交 2 条当天记忆（如「午后在便利店听到一首旧歌」「和同事争了一句」）并进入 `memory` 模式
- **THEN** 创建会话后依次返回 `director` 与 `dreamer` 回合
- **AND** 发送给两个 LLM 的 messages 包含这两条记忆作为潜在意象素材
- **AND** 回合文本不出现「你昨天/你说过」等事实性断言（内容闸门校验）

#### Scenario: 无记忆不可强制记忆梦
- **WHEN** 用户显式请求 `mode="memory"` 且 `day_memories` 为空
- **THEN** 接口返回 422，提示记忆梦至少需要一条当天记忆
- **AND** 不创建会话、不调用任何 LLM

#### Scenario: 原采集口径可回装
- **WHEN** 注入实现了 `MemorySource` 的 `CXOMemorySource`（包装原 `DreamMaterialCollector`）
- **THEN** `DreamTalkService` 使用其返回的记忆快照开始 `memory` 会话
- **AND** 核心编排代码不直接依赖 `MemoryManager` / `GraphRepository`

### Requirement: 双 LLM 梦境对话

系统 SHALL 由两个独立 LLM 角色交替推进梦境，每轮固定为「潜意识导演 → 梦者」两个回合：

- `director`（潜意识导演）：布置/切换场景，扮演梦中其他存在，制造偶然与转折；不得替梦者行动或内心独白；
- `dreamer`（梦者）：以第一人称在梦中行动、感受、变形；不得代替其他角色说话；
- 两者共享「梦的契约」：第一人称/意象化叙述、禁止断言用户真实经历、禁止解释或总结、禁止向用户提供选项或提问、不为现实问题提供建议；
- 每轮生成后写入会话记录；单会话默认最多 8 轮（可通过环境变量调整），达到上限自动结束；
- 上下文默认携带最近 16 个梦内回合，避免无限增长。

#### Scenario: 创建梦境会话
- **WHEN** 用户提交 1 条以上当天记忆并创建会话（模式为 `auto` 且判定为 `memory` 或 `wild`）
- **THEN** 系统依次生成 1 条 `director` 回合与 1 条 `dreamer` 回合并返回
- **AND** 两个回合均带 `speaker`、`content`、`seq`、`created_at`

#### Scenario: 双方不越权
- **WHEN** 任一方 LLM 输出中替另一方行动或说话
- **THEN** 系统提示词必须显式禁止该行为；验收用例校验提示词包含该约束

### Requirement: 梦境内外上下文隔离

系统 SHALL 在领域层强制区分「梦内上下文」与「清醒上下文」，二者不得隐式互通：

- **梦内上下文（DreamContext）** 仅允许包含：
  1. 本次入睡时解析出的 `MemoryMaterial` 快照（`day_memories` / `entities` / `emotion`）；
  2. 本次会话已产生的梦内回合（导演/梦者/醒者）；
  3. 模式指令与角色提示词。
- `MemoryMaterial` 只会**在入睡时解析一次**：`ManualMemorySource` 取自本次请求；`CXOMemorySource` 在回装后只读采集一次快照。梦中 LLM 不得在回合进行时直接查询记忆库/图谱；
- 梦内上下文 **禁止** 包含：梦外聊天记录、用户档案、其他会话、既往梦境的原始回合或摘要、服务端日志或任何环境中的其他会话数据；
- 唯一例外是用户主动以「醒者」身份发送的话，它作为梦内新回合进入，不携带任何外部历史；
- **清醒上下文（WakeContext）** 只允许消费 `DreamRecall`：`{session_id, created_at, mode, title, summary, emotion_residue}`；
- 原始梦境回合只能通过「梦境档案」界面回看，不得由清醒侧自动读取，更不得自动注入下一场梦；
- 下一场梦默认只使用新提交/新采集的记忆素材，不自动继承上一场梦境或摘要；若用户希望引用，必须自己把内容写入新的当天记忆。

#### Scenario: 梦内不读梦外
- **WHEN** 服务端存在任意梦外会话/用户档案文本（测试中以哨兵字符串模拟）并创建梦境会话
- **THEN** 发送给梦者与导演的全部 messages 中不出现该哨兵字符串
- **AND** `DreamDialogue.build_messages()` 只接受 `DreamContext`，不接受外部历史参数

#### Scenario: 醒后只取摘要
- **WHEN** 用户结束梦境并请求清醒侧上下文
- **THEN** `GET /api/sessions/{id}/recall` 只返回 `DreamRecall` 字段，不包含 `turns` 或原始回合文本
- **AND** `GET /api/recall` 返回最近若干条摘要级记录

#### Scenario: 不自动继承
- **WHEN** 用户连续创建两个梦境会话
- **THEN** 第二场会话的梦内 messages 不包含第一场的回合文本或摘要

### Requirement: 醒者介入

系统 SHALL 允许用户随时以 `awakened`（醒者）身份插入一条消息；该消息作为梦内事件立即写入会话，并触发新一轮「导演 + 梦者」共演，两者必须承接醒者的话：

- 允许空消息，等价于「继续做梦」，只推进一轮，不产生 `awakened` 回合；
- 会话进行中禁止重复创建同 ID 会话；同一会话的推进操作串行执行。

#### Scenario: 插话
- **WHEN** 用户在梦境进行中发送「我伸手推开那扇门」
- **THEN** 会话新增 1 条 `awakened` 回合，随后新增 `director` 与 `dreamer` 各 1 条回合
- **AND** 返回的回合顺序严格为 awakened → director → dreamer

#### Scenario: 继续做梦
- **WHEN** 用户发送空内容
- **THEN** 不新增 `awakened` 回合，仅新增 `director` 与 `dreamer` 回合

### Requirement: 模式自动决策

系统 SHALL 在创建会话时自动选择模式（`auto`），选择必须确定、可测试、带原因：

- 基础权重默认 `memory=0.5`、`wild=0.3`、`dreamless=0.2`，可由环境变量覆盖；
- 偏置规则（依次应用）：
  1. 无当天记忆 → `memory` 权重直接归零，`dreamless ×2.0`、`wild ×0.5`；
  2. 记忆 ≥ 3 条 → `dreamless ×0.5`、`wild ×1.2`；
  3. 情绪强度 `min(1, |valence| + arousal) ≥ 0.7` → `wild ×1.8`；
  4. 上一场会话为 `dreamless` → `dreamless ×0.3`（避免连续空白夜）；
- 权重归一化后按注入的随机源落入区间，返回 `mode` 与 `mode_reason`（中文，例如「今日记忆充足，织入梦境」「素材稀薄，今夜无梦」）；
- 显式传入 `mode`（`memory` / `wild` / `dreamless`）时跳过自动判定；`memory` 的素材前置校验仍生效。

#### Scenario: 空素材偏向无梦
- **WHEN** 未提供任何当天记忆且随机源落在无梦区间
- **THEN** 会话 `mode="dreamless"`，`mode_reason` 说明素材稀薄
- **AND** 自动模式绝不会选中 `memory`

#### Scenario: 高情绪偏向天马行空
- **WHEN** 情绪强度 ≥ 0.7 且随机源落在天马行空区间
- **THEN** 会话 `mode="wild"`，提示词切换为天马行空版本且 temperature 高于记忆梦

### Requirement: 一夜无梦

系统 SHALL 支持 `dreamless` 模式：

- 不发起任何 LLM 调用；
- 不生成 `director` / `dreamer` 回合；
- 会话创建后立即 `status="ended"`，`summary` 为安静的固定短句（含判定原因）；
- 接口与界面均正常返回，不视为错误。

#### Scenario: 无梦夜
- **WHEN** 创建会话被判定为 `dreamless`
- **THEN** 响应中 `turns` 为空数组、`status="ended"`、`summary` 非空
- **AND** 记录 LLM 调用次数的测试断言为 0

### Requirement: 天马行空

系统 SHALL 在 `wild` 模式下强化超现实自由度：

- 沿用本次 `MemoryMaterial` 作为出发点，但提示词额外允许时空跳跃、身份与场景重构、梦中梦、元叙事与意象拼贴；
- `director` / `dreamer` 的温度默认分别提高到 `1.0` / `1.1`（记忆梦为 `0.85` / `0.9`）；
- 前端展示「天马行空」标识与判定原因。

#### Scenario: 模式提示隔离
- **WHEN** 会话模式为 `wild`
- **THEN** 两个角色的 system prompt 均包含天马行空指令
- **AND** 会话记录中的 `mode` 为 `wild`

### Requirement: 梦境内容闸门

系统 SHALL 对每条 LLM 梦境回合执行确定性文本校验（移植并改造 CX-O `filter.py`）：

- 命中事实性断言模式（`你昨天…`、`你刚才…`、`你说过…`、`你曾经…`、`你做了…`、`我记得你…`）视为越界；
- 首次越界时，携带纠正提示让同一角色重写一次（仅一次）；
- 重写后仍越界：保留文本但标记 `flagged=true`，不阻断对话；
- 空文本视为失败并重试一次；仍为空则该回合以「（梦在这里断了一瞬）」占位。

#### Scenario: 事实断言改写
- **WHEN** `dreamer` 首次输出包含「你昨天答应过我」
- **THEN** 系统发起一次纠正重写
- **AND** 最终回合不得包含该事实断言；若仍包含则 `flagged=true`

### Requirement: 会话持久化与醒来摘要

系统 SHALL 使用 SQLite 持久化会话与回合：

- `sessions(id TEXT PK, created_at, mode, mode_reason, status, seeds_json, emotion_json, title, summary, emotion_residue_json, ended_at)`
- `turns(id INTEGER PK, session_id, seq, speaker, content, flagged, created_at)`
- 每个公开存储方法使用独立短连接（沿用 CX-O `buffer.py` 模式）；
- `POST /api/sessions/{id}/wake` 结束会话并生成 `DreamRecall`：标题（≤12 字）+「梦的余韵」（≤120 字）+ 情绪残留，由 `director` 客户端一次 LLM 调用产出；失败时降级为本地截断摘要，不报错；
- 达到最大轮数时会话自动结束，摘要按同一规则生成；
- 会话列表按创建时间倒序返回最近 20 条；
- 摘要生成后，`DreamRecall` 通过清醒侧接口暴露；原始回合仍只属于梦境档案。

#### Scenario: 醒来
- **WHEN** 用户点击「醒来」
- **THEN** 会话 `status="ended"`、写入 `title` / `summary` / `emotion_residue`、返回完整会话详情与 `recall`
- **AND** 再次调用 `wake` 或继续发言返回 409，不重复生成摘要

### Requirement: 可移植回 CX-O 的准备

系统 SHALL 以可整体回装的方式分层，核心不依赖任何 Web/存储/环境实现：

- `core/`（`models.py` / `modes.py` / `filter.py` / `dialogue.py` / `personas.py`）：纯领域逻辑，禁止导入 `fastapi`、`uvicorn`、`httpx`、`sqlite3`、`dotenv`、`os.environ`；
- `ports.py`：定义 `LLMClient`（`async chat(messages, *, temperature) -> str`）、`MemorySource`（`async collect(agent_id) -> MemoryMaterial`）、`SessionStore`、`RandomSource`、`Clock`、`EventSink` 协议；
- `adapters/`：`OpenAICompatibleClient`、`SQLiteSessionStore`、`EnvSettings`、`MockLLMClient`、`ManualMemorySource`，以及回装专用：
  - **`CXOModelRouterAdapter`**：包装 CX-O 风格 `router.get_client(model).chat(...)` 的鸭子类型客户端；
  - **`CXOMemorySource`**：包装原 `DreamMaterialCollector`（或任何暴露 `collect(agent_id)` 的对象），把快照映射为 `MemoryMaterial`，保留只读采集口径；
- `DreamTalkService` 门面：以构造注入方式接收上述端口，对外暴露 `start_session` / `interject` / `advance` / `wake` / `get_recall` / `list_recalls` / `get_session`，CX-O 可不经 HTTP 直接嵌入；
- `EventSink` 默认空实现；回装后可替换为 CX-O 的 WebSocket 广播，用于推送 `dream.session_started` / `dream.turn_added` / `dream.session_completed`（本独立项目不实现 WS）；
- 契约版本常量 `CONTRACT_VERSION = "1.0"` 出现在健康检查与会话 DTO；字段命名与 `docs/PORTING.md` 的映射表一致；
- `docs/PORTING.md` 必须包含：目录/模块映射到 CX-O 的建议位置、端口替换清单（LLM / MemorySource / Store / EventSink / Clock / RNG）、配置字段映射、上下文隔离保证、回装步骤与回归测试清单。

#### Scenario: 核心无基础设施依赖
- **WHEN** 对 `src/dreamtalk/core/**` 做静态扫描
- **THEN** 不存在 `fastapi` / `sqlite3` / `httpx` / `dotenv` / `uvicorn` 导入
- **AND** 不直接读取环境变量

#### Scenario: 无 HTTP 嵌入
- **WHEN** 测试用 Mock 客户端 + 内存存储 + 固定时钟 + `ManualMemorySource` 构造 `DreamTalkService`
- **THEN** 可完整跑通「创建 → 插话 → 醒来 → 取摘要」而不启动 FastAPI

#### Scenario: 记忆源可替换
- **WHEN** 将 `MemorySource` 从 `ManualMemorySource` 替换为 `CXOMemorySource`
- **THEN** 服务行为与接口不变，仅素材来源改变
- **AND** 核心 `core/` 代码无需修改

### Requirement: 对话 Web 界面

系统 SHALL 提供零构建、零 CDN 的单页对话界面（`web/index.html` + `app.js` + `styles.css`，由 FastAPI 静态挂载）：

- 入睡面板：多行「今天的记忆」输入、可选「零散意象」输入、情绪选择（平静/愉悦/低落/焦躁，映射 valence/arousal）、模式选择（自动/记忆梦/天马行空/一夜无梦）；
- 梦境视图：模式徽标与判定原因、按角色着色的回合流（梦者/潜意识/醒者）、可用「继续做梦」与「醒来」；
- 醒来视图：只展示摘要、标题与情绪残留，并明确提示「梦的原文仅存于梦境档案」；
- 无梦视图：安静的「今夜无梦」画面与原因，提供「再来一晚」；
- 历史会话侧栏：最近会话可回看梦境档案，并提供「只看梦醒摘要」视图；
- 所有交互仅依赖同源 `fetch`，无外部字体/脚本/图片资源。

#### Scenario: 无梦界面
- **WHEN** 会话被判定为 `dreamless`
- **THEN** 页面进入无梦视图，不显示输入框与继续按钮
- **AND** 显示判定原因

#### Scenario: 醒后摘要视图
- **WHEN** 用户点击「醒来」
- **THEN** 页面切换为摘要视图，不把原始回合作为清醒上下文展示
- **AND** 可通过「查看梦境档案」显式回看原文

#### Scenario: 记忆梦界面
- **WHEN** 用户在「今天的记忆」输入多条内容并选择「记忆梦」
- **THEN** 创建的会话 `mode="memory"`，素材随请求提交
- **AND** 界面不提供任何梦外聊天记录自动带入入口

### Requirement: LLM 适配与配置

系统 SHALL 通过 OpenAI 兼容的 `/chat/completions` 调用 LLM，并支持按角色覆盖模型：

- `DREAMTALK_BASE_URL`（默认 `https://api.openai.com/v1`）
- `DREAMTALK_API_KEY`（为空则降级 Mock）
- `DREAMTALK_MODEL`（默认 `gpt-4o-mini`）
- `DREAMTALK_DREAMER_MODEL` / `DREAMTALK_DIRECTOR_MODEL`（可选覆盖）
- `DREAMTALK_MOCK=1` 强制 Mock
- `DREAMTALK_MAX_ROUNDS`（默认 `8`）、`DREAMTALK_CONTEXT_TURNS`（默认 `16`）
- `DREAMTALK_MODE_WEIGHTS`（可选，形如 `memory=0.5,wild=0.3,dreamless=0.2`）
- `.env` 由 `python-dotenv` 自动加载，`.env.example` 提供注释模板

#### Scenario: 调用失败隔离
- **WHEN** LLM HTTP 调用超时或返回非 2xx
- **THEN** 该回合使用 Mock 风格兜底文本，不使请求 500
- **AND** 服务日志记录告警

## MODIFIED Requirements

### Requirement: 梦境生成（原单 LLM 候选生成）

原 `DreamGenerator` 以一条 prompt 批量生成 N 条候选、经 D7 闸门后入缓冲。本项目改为：

- 生成单位从「候选文本」变为「带说话人的回合」；
- 生成方式从「单次调用」变为「双角色多轮交替、每轮两次调用」；
- 输出不再进入主库缓冲，而是直接写入本项目的 `turns` 表；
- 原 `DreamConfig` 的采集窗口、TTL、固化重要性等字段不再适用，配置收敛为模式权重、轮数、上下文长度、温度与连接参数；
- 原「候选 → 用户确认」流程改为「梦内共演 → 醒来摘要」。

### Requirement: 素材采集（原只读采集器）

原 `DreamMaterialCollector` 的采集口径保留为 `MemorySource` 端口的一种实现：

- 独立项目默认 `ManualMemorySource`，素材来自用户提交的当天记忆；
- 回装 CX-O 时使用 `CXOMemorySource`，复现近 7 天边缘记忆、图谱孤立实体、最近日记情绪的只读采集；
- 无论哪种实现，都只在入睡时产出一次 `MemoryMaterial` 快照；梦境回合期间不直接访问记忆库/图谱。

## REMOVED Requirements

### Requirement: 昼夜调度与生理触发

**Reason**：独立对话项目没有常驻睡眠监测、心率设备与昼夜后台循环；触发改由用户「入睡」动作发起。
**Migration**：模式自动判定以「当天记忆 + 情绪 + 上一场模式」替代昼夜/生理信号；相关环境变量见 ADDED Requirements。

### Requirement: 主库固化、主动提起与缓冲审计

**Reason**：项目不依赖 CX-O 记忆库，也不存在后台候选待确认流程；且梦境外上下文只允许消费摘要。
**Migration**：梦境会话与回合独立落库；醒来摘要作为 `DreamRecall` 供清醒侧使用，不写入任何「真实记忆」，也不自动注入下一场梦。
