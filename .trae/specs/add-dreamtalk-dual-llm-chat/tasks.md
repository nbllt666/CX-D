# Tasks

- [x] Task 1: 从 CX-O 拆出梦境引擎并建立独立项目骨架
  - [x] SubTask 1.1: 新建 `src/dreamtalk/{core,adapters}/`，将 `C:\CX-O\CX-O-SERVER\server\autonomy\dream\` 中可复用资产（`collector.py` / `config.py` / `filter.py` / `buffer.py` / `summarizer.py` / `generator.py`）复制为项目内初始参考，随后删除与 CX-O 强耦合的部分（engine / sleep_sensor / physio / confirmation / consolidator / purge）
  - [x] SubTask 1.2: 编写 `pyproject.toml`（包名 `dreamtalk`、依赖 fastapi/uvicorn/httpx/python-dotenv、console script、pytest 配置）
  - [x] SubTask 1.3: 编写 `.gitignore`、`.env.example`、`src/dreamtalk/__init__.py`、`__main__.py`
  - [x] SubTask 1.4: 确认项目中不存在 `server.*` 导入与 CX-O 绝对路径

- [x] Task 2: 配置、端口与 LLM / 记忆源适配层
  - [x] SubTask 2.1: `core/models.py` 定义 `Message` / `Turn` / `DreamSession` / `DreamRecall` / `DreamContext` / `MemoryMaterial` / `Emotion` / `Mode`，并声明 `CONTRACT_VERSION = "1.0"`
  - [x] SubTask 2.2: `ports.py` 定义 `LLMClient`、`MemorySource`（`async collect(agent_id) -> MemoryMaterial`）、`SessionStore`、`RandomSource`、`Clock`、`EventSink` 协议（核心仅依赖协议）
  - [x] SubTask 2.3: `adapters/settings.py` 基于环境变量的 `Settings`（base_url/api_key/model/角色模型覆盖/mock 开关/最大轮数/上下文回合/模式权重/数据目录/温度），自动加载 `.env`，非法值回退默认；核心不得直接读环境变量
  - [x] SubTask 2.4: `adapters/llm.py` 实现 `OpenAICompatibleClient`（httpx 调用 `/chat/completions`，超时与异常降级为 Mock 文本）、`MockLLMClient`（确定性中文梦境文本、记录调用次数）与 `CXOModelRouterAdapter`（包装 CX-O 风格 `router.get_client(model).chat(...)`）
  - [x] SubTask 2.5: `adapters/memory.py` 实现 `ManualMemorySource`（当日记忆来自请求）与 `CXOMemorySource`（包装原 `DreamMaterialCollector` 或任何暴露 `collect(agent_id)` 的对象，映射为 `MemoryMaterial`）；采集异常降级为空快照
  - [x] SubTask 2.6: `adapters/store.py` 实现 SQLite 短连接存储：`sessions` / `turns` 建表、创建/读取/列表/追加回合/结束会话/摘要更新，回合序号单调递增；另实现测试用 `MemorySessionStore`

- [x] Task 3: 模式自动决策
  - [x] SubTask 3.1: `core/modes.py` 实现 `select_mode(memories, emotion, weights, rng, forced, last_mode)`，返回 `(mode, reason)`
  - [x] SubTask 3.2: 落地权重偏置规则、无记忆时 `memory` 权重归零、归一化与显式模式短路
  - [x] SubTask 3.3: 测试覆盖：空素材绝不选记忆梦且偏无梦、记忆充足提升常态选择、高情绪提升天马行空、连续无梦衰减、显式模式优先、确定性随机源

- [x] Task 4: 梦境内容闸门
  - [x] SubTask 4.1: `core/filter.py` 移植事实性断言正则，改为 `check_text(text) -> list[str]` 的无状态校验
  - [x] SubTask 4.2: 在编排层实现「首次越界 → 纠正重写一次 → 仍越界标记 flagged」与空文本重试/占位
  - [x] SubTask 4.3: 测试覆盖：六类断言命中、正常梦境文本放行、重写后通过、重写后仍越界标记

- [x] Task 5: 双 LLM 对话编排（含记忆梦与上下文隔离）
  - [x] SubTask 5.1: `core/personas.py` 编写梦者/潜意识导演的记忆梦与天马行空 system prompt（含不越权、不提供选项、不解释、不断言真实经历、记忆碎片只作潜在意象）
  - [x] SubTask 5.2: `core/dialogue.py` 实现 `DreamDialogue`：`build_messages()` 只接受 `DreamContext`（`MemoryMaterial` + 梦内回合 + 模式）；`start()`（模式判定、无梦短路、导演+梦者开场）、`interject()`（醒者回合 + 一轮共演）、`advance()`、`wake()`（`DreamRecall` / 幂等 409）、最大轮数自动结束、同会话推进串行化
  - [x] SubTask 5.3: 强制显式 `memory` 且无当天记忆时拒绝（业务异常，由 API 映射 422）
  - [x] SubTask 5.4: 明确禁止将梦外历史、既往梦境回合或摘要自动注入 `DreamContext`；下一场梦只使用新素材
  - [x] SubTask 5.5: 测试覆盖：记忆梦开场顺序、插话顺序、空消息、无梦零 LLM 调用、最大轮数自动结束、重复 wake/继续返回冲突、摘要降级、无记忆强制记忆梦被拒
  - [x] SubTask 5.6: 隔离测试：在服务端放置梦外哨兵文本，断言发送给两个 LLM 的 messages 不含哨兵；连续两场会话不互相携带回合

- [x] Task 6: DreamTalkService 门面与事件端口
  - [x] SubTask 6.1: `service.py` 实现 `DreamTalkService`：构造注入 `LLMClient ×2` / `SessionStore` / `MemorySource`（可选）/ `RandomSource` / `Clock` / `EventSink`，对外暴露 `start_session` / `interject` / `advance` / `wake` / `get_recall` / `list_recalls` / `get_session`
  - [x] SubTask 6.2: 素材解析顺序：注入 `MemorySource` 时使用其快照（失败回退请求素材），否则使用请求中的 `day_memories` / `entities` / `emotion`
  - [x] SubTask 6.3: `EventSink` 空实现为默认，编排中在会话开始/回合新增/会话结束时发事件（供回装 CX-O 后接 WebSocket）
  - [x] SubTask 6.4: 测试：用 Mock 客户端 + 内存存储 + 固定时钟 + `ManualMemorySource`，不启动 FastAPI 跑通「创建 → 插话 → 醒来 → 取摘要」；替换 `CXOMemorySource` 后接口行为不变

- [x] Task 7: FastAPI 接口（梦境面 / 清醒面分离）
  - [x] SubTask 7.1: `api.py` 提供 `GET /api/health`、`POST /api/sessions`（仅接受 `day_memories` / `entities` / `emotion` / `mode`）、`GET /api/sessions`、`GET /api/sessions/{id}`（梦境档案）、`POST /api/sessions/{id}/message`、`POST /api/sessions/{id}/wake`
  - [x] SubTask 7.2: 清醒面接口 `GET /api/sessions/{id}/recall` 与 `GET /api/recall`，响应只含 `DreamRecall` 字段，不含回合
  - [x] SubTask 7.3: 定义请求/响应模型与错误码（404/409/422；`mode="memory"` 且无 `day_memories` → 422）；`POST /api/sessions` 拒绝任何外部上下文注入字段
  - [x] SubTask 7.4: 测试：Mock 下完整 HTTP 流程（创建→插话→醒来→recall→历史）、记忆梦素材传递、无梦响应、404/409/422、recall 不含 turns

- [x] Task 8: Web 对话界面
  - [x] SubTask 8.1: 挂载 `web/` 静态资源，`/` 返回对话页
  - [x] SubTask 8.2: 编写 `web/index.html` / `styles.css` / `app.js`：入睡面板（「今天的记忆」多行输入、可选「零散意象」、情绪、模式）、梦境回合流、醒来摘要视图、梦境档案回看、无梦视图、继续/醒来、历史侧栏；零外部资源
  - [x] SubTask 8.3: 界面文案明确「梦内 / 梦外」边界：醒来默认只看摘要，档案需显式打开；不提供任何梦外聊天记录自动带入入口

- [x] Task 9: 可移植性文档与打包验收
  - [x] SubTask 9.1: 编写 `docs/PORTING.md`：模块映射到 CX-O 建议位置（含 `collector.py → CXOMemorySource`）、端口替换清单（LLM / MemorySource / Store / EventSink / Clock / RNG）、配置字段映射、上下文隔离保证、回装步骤与回归测试清单
  - [x] SubTask 9.2: 编写中文 `README.md`（项目定位、与 CX-O 的关系、三种模式、安装/配置/启动、上下文隔离、API、测试、目录结构）
  - [x] SubTask 9.3: `pip install -e .` 后运行 `pytest` 全绿
  - [x] SubTask 9.4: 以 Mock 模式启动服务，走通「记忆梦入睡 → 插话 → 继续 → 醒来 → 摘要/档案」与「一夜无梦」两条链路
  - [x] SubTask 9.5: 检查打包产物：无 CX-O 运行期依赖、核心层无基础设施导入、无明文密钥、无运行期数据误提交

# Task Dependencies

- Task 2 依赖 Task 1
- Task 3、Task 4 依赖 Task 2，可并行
- Task 5 依赖 Task 2、Task 3、Task 4
- Task 6 依赖 Task 5
- Task 7 依赖 Task 6
- Task 8 依赖 Task 7
- Task 9 依赖 Task 8
