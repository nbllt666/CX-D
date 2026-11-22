# DreamTalk → CX-O 移植指南

本项目按「核心 / 端口 / 适配器」三层组织，目的就是**整体装回 CX-O** 时只替换适配器，不改梦境编排。
本文件给出模块映射、端口替换、配置映射、隔离保证、回装步骤与回归清单。

## 1. 分层与模块映射

| DreamTalk | 建议落位（CX-O） | 说明 |
| --- | --- | --- |
| `src/dreamtalk/core/models.py` | `server/autonomy/dream/contracts.py` | `DreamSession` / `Turn` / `DreamRecall` / `MemoryMaterial`；契约版本 `1.0` |
| `src/dreamtalk/core/modes.py` | `server/autonomy/dream/modes.py` | 记忆梦 / 天马行空 / 一夜无梦的自动决策 |
| `src/dreamtalk/core/filter.py` | `server/autonomy/dream/filter.py` | 原 `DreamFilter` 的确定性规则迁移为 `check_text` |
| `src/dreamtalk/core/personas.py` | `server/autonomy/dream/personas.py` | 梦者 / 潜意识导演提示词 |
| `src/dreamtalk/core/dialogue.py` | `server/autonomy/dream/dialogue.py` | 双 LLM 编排、醒来摘要、事件 |
| `src/dreamtalk/ports.py` | `server/autonomy/dream/ports.py` | LLM / MemorySource / Store / Clock / RNG / EventSink 协议 |
| `src/dreamtalk/service.py` | `server/autonomy/dream/service.py` | `DreamTalkService` 门面，可直接被引擎/路由调用 |
| `src/dreamtalk/adapters/llm.py` | `server/autonomy/dream/adapters/llm.py` | OpenAI 客户端、Mock、`CXOModelRouterAdapter` |
| `src/dreamtalk/adapters/memory.py` | `server/autonomy/dream/adapters/memory.py` | `ManualMemorySource` / `CXOMemorySource` |
| `src/dreamtalk/adapters/store.py` | `server/autonomy/dream/adapters/store.py` | SQLite 会话存储（可换 CX-O 存储） |
| `src/dreamtalk/api.py` | `server/api/routers/dream.py` | 会话式梦境路由（梦境面 + 清醒面） |
| `web/` | `APP-Frontend/src/pages/DreamPage` 或独立静态页 | 对话界面 |

核心层禁止导入 `fastapi` / `sqlite3` / `httpx` / `dotenv` / `uvicorn` / `os`，也不直接读环境变量；
这一约束由 `tests/test_core_purity.py` 守护。

## 2. 端口替换清单

| 端口 | 独立项目实现 | CX-O 回装实现 |
| --- | --- | --- |
| `LLMClient` | `OpenAICompatibleClient` / `MockLLMClient` | `CXOModelRouterAdapter(router, model)`，直接复用 CX-O 模型路由 |
| `MemorySource` | `ManualMemorySource` | `CXOMemorySource(collector)`，包装原 `DreamMaterialCollector` |
| `SessionStore` | `SQLiteSessionStore` | 可继续使用 SQLite，或实现 CX-O 存储适配器 |
| `EventSink` | 空实现 | 包装 `ws_manager.broadcast`，推送 `dream.*` 事件 |
| `Clock` | `datetime.now()` | CX-O 统一时钟（若有） |
| `RandomSource` | `random.random()` | CX-O 可注入的随机源 / 测试固定值 |

### LLM 回装示例

```python
from dreamtalk.adapters.llm import CXOModelRouterAdapter

dreamer = CXOModelRouterAdapter(model_router, "summary")
director = CXOModelRouterAdapter(model_router, "summary")
```

`CXOModelRouterAdapter` 兼容 `client.chat(messages=..., stream=False, temperature=...)`
的响应形态（带 `.content` 或纯字符串），调用失败会降级为离线文本。

### 记忆源回装示例

```python
from dreamtalk.adapters.memory import CXOMemorySource

collector = DreamMaterialCollector(memory_manager, graph_repo, config)
memory_source = CXOMemorySource(collector)  # collect(agent_id) 只读采集一次
```

`CXOMemorySource` 接受任何暴露 `collect(agent_id)` 的对象，快照可为 dataclass 或 dict；
映射字段：`memories[*].content` → `day_memories`、`isolated_entities` → `entities`、
`emotion_baseline` → `emotion.valence`。采集失败返回空素材，由服务层回退请求素材。

### 事件回装示例

```python
class WSEventSink:
    def __init__(self, ws_manager):
        self._ws = ws_manager

    async def emit(self, event_type, data):
        await self._ws.broadcast({"type": event_type, "data": data})
```

事件类型：`dream.session_started` / `dream.turn_added` / `dream.session_completed`。

## 3. 配置映射

| DreamTalk | CX-O 建议落点 | 说明 |
| --- | --- | --- |
| `DREAMTALK_MODEL` / 角色模型覆盖 | `DreamConfig.model` / 模型路由 | 回装后由 `CXOModelRouterAdapter` 决定模型 |
| `DREAMTALK_MAX_ROUNDS` | 新增 `DreamConfig.max_rounds` | 双 LLM 轮数上限 |
| `DREAMTALK_CONTEXT_TURNS` | 新增 `DreamConfig.context_turns` | 每次携带的最近梦内回合 |
| 记忆梦温度 `0.85 / 0.9` | `DreamConfig.dream_temperature` 语义替代 | 建议新增 `director_temperature` / `dreamer_temperature` |
| 天马行空温度 `1.0 / 1.1` | 新增 `DreamConfig.wild_*` | 可沿用 `dream_temperature` 扩展 |
| `DREAMTALK_MODE_WEIGHTS` | 新增 `DreamConfig.mode_weights` | 默认 `memory=0.5,wild=0.3,dreamless=0.2` |
| `DREAMTALK_DATA_DIR` | `server/autonomy/data/` | 沿用 CX-O 数据目录 |
| `DreamConfig.schedule` / `physio` / `trigger` | 保留在 CX-O 侧 | 与对话式梦境解耦；如仍需定时入睡，由引擎调用 `start_session` |

原 `DreamConfig` 的 `material_window_days` / `max_material_items` / `min_lucidity` /
`dream_ttl_hours` / `purge_threshold` / `confirmed_importance` 不再驱动本编排；
采集窗口与上限属于 `CXOMemorySource` 内部（沿用原 collector）。

## 4. 上下文隔离保证

回装时必须保持以下边界：

1. **素材只解析一次**：`CXOMemorySource` 在 `start_session` 内调用一次 `collector.collect(agent_id)`，
   得到 `MemoryMaterial` 快照；之后的回合不再访问 `memory_manager` / `graph_repo`。
2. **提示词只含快照**：`DreamDialogue.build_messages` 只接收 `DreamContext`
   （素材快照 + 本会话回合 + 模式），没有 `history` 参数。
3. **不自动继承**：创建新会话时不读取上一场梦的回合或摘要；如需引用，让用户写入新素材。
4. **清醒侧只读摘要**：`get_recall` / `list_recalls` 返回 `DreamRecall`，不含 `turns`；
   梦境原文只在梦境档案接口中返回。
5. **醒者例外**：用户主动发送的「醒者」消息作为梦内新回合进入，不携带梦外历史。
6. **事件不含越界上下文**：`EventSink` 只应转发会话状态与回合，不拼接梦外聊天记录。

## 5. 回装步骤

1. 将 `core/`、`ports.py`、`service.py` 复制到 `server/autonomy/dream/`，保持包内相对导入；
2. 将 `adapters/llm.py`、`adapters/memory.py`、`adapters/store.py` 放入 `server/autonomy/dream/adapters/`；
3. 在 `server/autonomy/main.py`（或梦境的装配入口）构造：
   ```python
   service = DreamTalkService(
       dreamer=CXOModelRouterAdapter(model_router, config.model),
       director=CXOModelRouterAdapter(model_router, config.model),
       store=SQLiteSessionStore(data_dir / "dreamtalk.db"),
       memory_source=CXOMemorySource(DreamMaterialCollector(memory_manager, graph_repo, config)),
       events=WSEventSink(ws_manager),
       dialogue_config=DialogueConfig(max_rounds=..., context_turns=...),
       mode_weights=ModeWeights(...),
   )
   ```
4. 在 `server/api/routers/dream.py` 中挂载新的会话式路由；
   旧的 `status/trigger/list/confirm/reject/purge/config` 可按团队策略保留只读兼容或下线；
5. 若仍需昼夜触发：在 `DreamEngine._run_loop` 的睡眠窗口边沿调用 `service.start_session()`，
   入睡确认/首步摘要仍由 CX-O 侧负责，不进入 `core/`；
6. 配置迁移：把新增字段加入 `UnifiedConfig` 与 `dream_config.schema.json`；
7. 运行第 6 节回归清单。

## 6. 回归测试清单

- [ ] `tests/test_core_purity.py` 等价扫描通过：核心层无基础设施依赖
- [ ] `test_context_isolation_between_sessions`：梦外/上一场梦的哨兵文本不出现在 LLM messages
- [ ] `test_build_messages_only_accepts_dream_context`：提示词构造函数没有外部历史入口
- [ ] `test_dreamless_uses_zero_llm_calls`：一夜无梦零 LLM 调用
- [ ] `test_forced_memory_without_memories_rejected`：记忆梦无当天记忆被拒
- [ ] `test_recall_requires_ended_session` 与 API `recall` 不含 `turns`
- [ ] `CXOMemorySource` 对原 collector 快照的字段映射（含采集失败降级）
- [ ] `dream.session_started` / `dream.turn_added` / `dream.session_completed` 事件被 WS 正确广播
- [ ] 连续两场会话不自动继承；新会话只使用新素材
- [ ] `python -m dreamtalk` 与 CX-O 内嵌两种启动方式都能完成「入睡 → 插话 → 醒来 → 取摘要」

## 7. 契约与兼容性

- 契约版本：`dreamtalk.CONTRACT_VERSION = "1.0"`，同时出现在 `/api/health` 与会话 DTO；
- 会话字段：`id / created_at / mode / mode_reason / status / day_memories / entities /
  emotion / material_source / title / summary / emotion_residue / ended_at / turn_count`；
- 回合字段：`seq / speaker / content / flagged / created_at`；
- 摘要字段：`session_id / created_at / mode / title / summary / emotion_residue`；
- 变更字段应先更新 `CONTRACT_VERSION`、`contracts.py` 与本文档，再同步适配器与前端。
