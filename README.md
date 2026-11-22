# CX-D（梦话 DreamTalk）

> 梦者 × 潜意识导演，两个 LLM 在夜里共演一场梦。
> 从 CX-O 梦境引擎拆出、重写并打包的独立对话项目。

DreamTalk 不是助手式的问答，而是一场由两个角色实时接力的梦境：

- **潜意识导演**：布置场景、制造偶然与转折，扮演梦中其他存在；
- **梦者**：以第一人称在梦里行动、感受、变形；
- **醒者**：随时可以插一句话，改变梦的走向。

没有选项、属性或掷骰子——自由度高过文字 RPG，梦自己往前走。

## 三种模式

| 模式 | 说明 |
| --- | --- |
| `memory` 记忆梦 | 原 CX-O 梦境引擎的定位：把当天/近期记忆碎片作为潜在意象，变形、凝缩、移置后入梦 |
| `wild` 天马行空 | 在记忆碎片之上允许时空跳跃、身份漂移、梦中梦与元叙事，逻辑刻意失稳 |
| `dreamless` 一夜无梦 | 不调用任何 LLM，不产生对话，只留下安静的「无梦」记录与原因 |

默认由系统自动决定当夜模式：素材稀薄更易无梦，记忆充足更易成梦，情绪翻涌更易天马行空；
也可以在界面上显式指定。

## 梦境内外上下文隔离

这是本项目的硬约束：

- 梦中 LLM 只能看见**本次入睡时解析出的记忆素材快照**和**本场梦的回合**；
- 不会读取梦外聊天记录、用户档案、其他会话或既往梦境；
- 醒来后，梦外只拿到 `DreamRecall`（标题 + 余韵 + 情绪残留），原始回合只留在「梦境档案」里；
- 下一场梦不会自动继承上一场梦的回合或摘要。

## 快速开始

要求 Python 3.11+。

```powershell
cd c:\CX-D
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

不配置任何密钥也能运行：系统会自动进入 Mock 模式，用确定性的离线文本演出完整梦境。

```powershell
python -m dreamtalk
```

打开 <http://127.0.0.1:8000>。

### 接入真实 LLM

复制 `.env.example` 为 `.env`，填写任意 OpenAI 兼容服务：

```dotenv
DREAMTALK_BASE_URL=https://api.openai.com/v1
DREAMTALK_API_KEY=sk-...
DREAMTALK_MODEL=gpt-4o-mini
# 可选：两个角色分别用不同模型
DREAMTALK_DREAMER_MODEL=
DREAMTALK_DIRECTOR_MODEL=
```

未配置 `DREAMTALK_API_KEY` 或设置 `DREAMTALK_MOCK=1` 时始终使用 Mock。
单次 LLM 调用失败会自动降级为离线文本，不会中断整场梦。

### 接入 Docker 中的 LLM（vLLM）

如果 LLM 是 CX-O 仓库里的 vLLM 容器（`docker/compose/docker-compose.llm.yml`，
宿主端口默认 `8080`），DreamTalk 在宿主机上运行时使用：

```dotenv
DREAMTALK_BASE_URL=http://127.0.0.1:8080/v1
DREAMTALK_API_KEY=local
DREAMTALK_MODEL=auto
```

- vLLM 默认不校验 Key，`local` 只是占位值，避免被判定为 Mock；
- `DREAMTALK_MODEL=auto` 会在首次调用时请求 `/v1/models` 自动发现实际模型名，
  不依赖 vLLM 的 `--served-model-name` 设置；
- 本地 / 内网地址默认绕过系统代理，避免 Windows 代理把 localhost 请求转成 502；
- 若 DreamTalk 之后也放进 Docker，并与 LLM 同处 `cxo-inference` 网络，
  把地址改为 `http://llm:8080/v1` 即可。

启动 LLM 容器并确认就绪：

```powershell
cd C:\CX-O
docker compose -f docker/compose/docker-compose.llm.yml --profile llm up -d
Invoke-RestMethod http://127.0.0.1:8080/v1/models
```

然后启动 DreamTalk。容器未就绪时，DreamTalk 会逐回合回退到离线文本；
服务恢复后，后续回合会自动重新尝试真实模型。

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DREAMTALK_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容接口地址 |
| `DREAMTALK_API_KEY` | 空 | 留空进入 Mock |
| `DREAMTALK_MODEL` | `gpt-4o-mini` | 默认模型；`auto` 时自动发现 |
| `DREAMTALK_DREAMER_MODEL` | 空 | 梦者模型覆盖 |
| `DREAMTALK_DIRECTOR_MODEL` | 空 | 导演模型覆盖 |
| `DREAMTALK_MOCK` | `0` | 强制离线 Mock |
| `DREAMTALK_MAX_ROUNDS` | `8` | 单场最多轮数（每轮导演 + 梦者） |
| `DREAMTALK_CONTEXT_TURNS` | `16` | 携带的最近梦内回合数 |
| `DREAMTALK_MODE_WEIGHTS` | `memory=0.5,wild=0.3,dreamless=0.2` | 自动模式权重 |
| `DREAMTALK_DATA_DIR` | `data` | SQLite 数据目录 |
| `DREAMTALK_HOST` / `DREAMTALK_PORT` | `127.0.0.1` / `8000` | 监听地址 |
| `DREAMTALK_TIMEOUT` | `60` | LLM 请求超时秒数 |
| `DREAMTALK_TRUST_ENV` | `auto` | 本地/内网自动绕过系统代理；`0`/`1` 显式覆盖 |

## HTTP API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查、Mock 状态与契约版本 |
| `POST` | `/api/sessions` | 入睡：`day_memories` / `entities` / `emotion` / `mode` |
| `GET` | `/api/sessions` | 最近 20 场会话（不含回合） |
| `GET` | `/api/sessions/{id}` | 梦境档案：会话 + 全部回合 |
| `POST` | `/api/sessions/{id}/message` | 醒者插话（空内容 = 继续做梦） |
| `POST` | `/api/sessions/{id}/wake` | 醒来并生成摘要 |
| `GET` | `/api/sessions/{id}/recall` | 清醒面：只返回摘要 |
| `GET` | `/api/recall` | 最近若干条醒来摘要 |

`POST /api/sessions` 使用 `extra="forbid"`：任何梦外上下文注入字段都会被 422 拒绝。

睡眠示例：

```json
{
  "day_memories": ["午后在便利店听到一首旧歌", "和同事争了一句"],
  "entities": ["旧钥匙"],
  "emotion": {"valence": -0.3, "arousal": 0.5},
  "mode": "auto"
}
```

## 测试

```powershell
pytest
```

覆盖模式决策、内容闸门、上下文隔离、双 LLM 编排、SQLite 存储与 API 主链路。

## 目录结构

```
src/dreamtalk/
  core/          纯领域：模型、模式、提示词、闸门、对话编排
  adapters/      OpenAI / Mock / 记忆源 / SQLite / 环境配置
  ports.py       端口协议
  service.py     DreamTalkService 门面（可被 CX-O 直接嵌入）
  api.py         FastAPI 接口（梦境面 / 清醒面）
  __main__.py    python -m dreamtalk
web/             零构建对话界面
tests/           pytest
docs/PORTING.md  回装 CX-O 的移植指南
```

## 与 CX-O 的关系

本项目从 `C:\CX-O\CX-O-SERVER\server\autonomy\dream\` 拆出，保留了：

- 事实性断言闸门的确定性规则；
- SQLite 短连接存储模式；
- 醒来摘要的思路；
- 原采集器的记忆采集口径（通过 `CXOMemorySource` 适配器）。

移除了昼夜调度、生理传感器、主库固化、后台自主循环与 WebSocket 协议。
后续可参考 [docs/PORTING.md](docs/PORTING.md) 将本项目整体装回 CX-O。
