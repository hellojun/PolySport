# MiroFish NBA 预测引擎 — 产品 & 架构文档

## 项目路径

```
/Users/huanleduo/Desktop/FFAI/github/AIxC-Tech/MiroFish
```

---

# 一、产品概述

## 1.1 产品定位

将 MiroFish 从通用社会模拟引擎改造为 **NBA 比赛预测工具**。核心价值：用多个具有不同分析风格和认知偏差的 AI 分析师，对 NBA 比赛进行结构化辩论，输出明确的投注建议，帮助用户在 Polymarket 等预测市场做出更好的决策。

## 1.2 目标用户

Polymarket NBA 玩家，有一定篮球认知，希望在下注前获得多维度系统化分析。

## 1.3 产品形态

- **Web 端**：预测详情页，展示完整分析过程和结果
- **Chrome 插件（Phase 2）**：自动读取用户正在浏览的 Polymarket 页面，在 popup 中展示简短预测卡片，点击跳转 Web 端看详情

## 1.4 未来扩展

可扩展至足球（世界杯）等体育赛事。

---

# 二、改造全景（11 项改动）

以下 11 项改动覆盖了从数据输入到结果输出的完整链路。每项标注了所属阶段。

| # | 改动项 | 阶段 | 概述 |
|---|--------|------|------|
| 1 | 本体改造 | Phase 1 | 从 LLM 动态生成改为 NBA 固定本体 |
| 2 | 报告改造 | Phase 1 | 从长篇报告改为分层预测卡片 |
| 3 | 数据源改造 | Phase 1 | NBA Stats API 自动拉取球队/球员/伤病数据；Polymarket 赔率 Phase 1 用户手动输入，Phase 2 插件自动读取 |
| 4 | Agent 角色体系 | Phase 1 | 从社媒用户改为 6 个专业分析师角色 |
| 5 | 模拟机制改造 | Phase 1 | 从社媒互动改为结构化辩论 |
| 6 | 记忆更新改造 | Phase 1 | 从社媒行为改为写入比赛结果和数据更新 |
| 7 | Polymarket 数据闭环 | Phase 2 | 插件自动读取赔率，赛后结算 |
| 8 | 输出格式改造 | Phase 1 | 分层输出 L1/L2/L3 |
| 9 | 用户输入改造 | Phase 2 | Chrome 插件自动读取 Polymarket 页面 |
| 10 | 回测与校准 | Phase 3 | 追踪预测准确率，调整 Agent 权重 |
| 11 | 运动类型抽象 | Phase 3 | 抽象 SportConfig 基类，为足球预留 |

---

# 三、Phase 1 — MVP

> 目标：跑通从用户输入到预测输出的完整链路，验证辩论式预测的可行性。

## Phase 1 覆盖的改动项

**#1 本体改造、#2 报告改造、#3 数据源改造（NBA Stats 部分）、#4 Agent 角色体系、#5 模拟机制改造、#6 记忆更新改造、#8 输出格式改造**

## 3.1 用户输入（#9 的 MVP 降级方案）

用户在 Web 页面手动输入，不做 Chrome 插件。

**必填项：**
- 主队名称 & 缩写（如 Philadelphia 76ers / PHI）
- 客队名称 & 缩写（如 Miami Heat / MIA）

**选填项（填写越多预测越准）：**
- Polymarket 市场赔率（胜负线、让分盘、总分盘的概率和盘口值）
- 交易量
- 比赛日期和时间
- 自由文本补充信息

**自动获取（来自 NBA Stats API，用户无需填写）：**
- 两队战绩
- 两队近期表现
- 核心球员伤病情况

## 3.2 NBA 数据自动拉取（#3）

**现状**：原 MiroFish 让用户上传 PDF/MD/TXT 文档，从中提取文本构建图谱。

**改为**：用户只需输入比赛场次（主客队）和时间，系统自动从 NBA Stats API 拉取该场比赛相关的结构化数据：

| 数据类型 | 来源 | 频率 |
|---------|------|------|
| 球队/球员基础信息 | NBA Stats API / Basketball Reference | 赛季初一次，有变动更新 |
| 赛季数据（场均、排名） | NBA Stats API | 每日更新 |
| 伤病报告 | ESPN / Official NBA Injury Report | 赛前更新 |
| 历史对战记录 | Basketball Reference | 按需 |

数据拉回后转为文本描述，通过现有 `graph_builder.add_text_batches()` 注入持久化 Zep 图谱。

Polymarket 赔率数据在 Phase 1 **由用户手动输入**（通过 Web 表单），Phase 2 改为 Chrome 插件从页面自动读取。

## 3.4 固定 NBA 本体（#1）

**现状**：`ontology_generator.py` 让 LLM 每次动态生成实体和关系类型，prompt 围绕"社交媒体舆论模拟"设计。

**改为**：硬编码 NBA 固定本体，跳过 LLM 调用，直接传给 `graph_builder.set_ontology()`。

NBA 实体类型（遵守 Zep 最多 10 个的限制）：
- Team、Player、Coach、Arena、Injury、GameRecord、Division、Season
- Person、Organization（兜底，与原系统逻辑一致）

NBA 关系类型：
- PLAYS_FOR、COACHES、HAS_INJURY、DEFEATED、HOME_COURT、BELONGS_TO、PLAYED_IN、TEAMMATE

## 3.5 分析师 Agent 角色体系（#4）

**现状**：`oasis_profile_generator.py` 从图谱实体生成社交媒体用户人设。

**改为**：预定义 6 个专业分析师角色，每个有独特的分析风格和**认知偏差**。偏差导致分歧，分歧才有预测价值。

| 角色 | 关注领域 | 认知偏差 |
|------|---------|---------|
| 统计分析师 | PER, TS%, 进攻/防守效率 | 过度信赖数据，忽略软因素 |
| 投注专家 | 赔率变动、市场效率、交易量 | 逆向思维，喜欢和市场对着干 |
| 伤病分析师 | 伤病报告、体能、背靠背 | 高估伤病影响，置信度偏低 |
| 战术分析师 | 对位匹配、教练调整、战术体系 | 过度解读战术匹配 |
| 状态分析师 | 近5-10场趋势、连胜连败、士气 | 严重近因偏差 |
| 主场分析师 | 主客场差异、旅行疲劳、赛程密度 | 高估主场优势 |

每个 Agent 是一个 system prompt 模板，运行时注入比赛数据和图谱上下文。Agent 必须以 JSON 格式返回预测结果（使用现有 `llm_client.chat_json()`）。

## 3.6 辩论引擎（#5）

**现状**：通过 OASIS 子进程运行 Twitter/Reddit 社媒模拟，有复杂的 IPC 机制。

**改为**：结构化辩论，3 轮制：
- **Round 1**：各分析师独立预测（不看别人的结果）
- **Round 2**：看到所有人 Round 1 的结果后，可修改或坚持，需说明原因
- **Round 3**：最终预测

辩论在 Python 主进程中串行调用 LLM，包在异步任务线程中不阻塞 API。通过现有 `TaskManager` 管理进度。

不再需要 OASIS 相关的 `simulation_runner.py`、`simulation_ipc.py`、`simulation_config_generator.py`。

## 3.7 预测结果分层输出（#2 + #8）

**现状**：`report_agent.py` 生成长篇 Markdown 报告，结论含糊。

**改为**：三层输出，默认展示 L1，可展开看更多。

**L1 — 预测卡片（首屏）：**

针对三个市场（胜负、让分、总分），每个展示：
- Pick（选哪边）
- 模型概率（分析师投票汇总）
- 市场概率（Polymarket 定价）
- Edge（模型概率 - 市场概率）
- 投注建议：value_bet（edge≥8%）/ lean（3-8%）/ no_edge（±3%）/ fade（≤-8%）
- 一句话理由

**L2 — 关键因素（可展开）：**
- 3-5 条影响预测的关键因素，标注来源分析师
- 分析师共识度：全票一致 / 强共识 / 轻微共识 / 严重分歧

**L3 — 完整辩论记录（可展开）：**
- 3 轮 × 6 个分析师的完整预测和理由
- 观点变化轨迹

## 3.8 记忆更新改造（#6）

**现状**：`zep_graph_memory_updater.py` 将社媒行为（发帖、点赞、转发）转为自然语言写入图谱。

**改为**：写入的内容变成比赛结果和 NBA 数据更新：
- 比赛结果：`"76人 112-105 击败 热火，2026-03-28"`
- 球员表现：`"Embiid 32分11篮板，投篮 12/22"`
- 伤病变动：`"Embiid 列为 questionable，膝伤"`
- 赛季数据更新：`"76人赛季战绩更新为 42-33"`

复用 `zep_graph_memory_updater.py` 的核心架构（后台线程 + 批量写入 + 重试机制），改写数据结构从 `AgentActivity`（社媒行为）变为 `NBADataUpdate`（比赛/数据更新）。

图谱的时间维度（Zep edge 的 `valid_at` / `invalid_at`）在此特别有用，可追踪球员状态和球队表现随时间的变化。

## 3.9 前端

新增一个 `/predict` 页面，三个状态：输入表单 → 进度条 → 预测结果。与原有页面独立。

## 3.10 Phase 1 图谱策略

Phase 1 使用**持久化图谱**。按赛季维护一个主图谱，通过 `data_fetcher` 每日增量写入球队/球员/伤病数据。预测时直接从主图谱检索上下文，不再每次新建。用户手动输入的 Polymarket 赔率和补充信息也写入图谱。旧数据通过 Zep 的 `invalid_at` / `expired_at` 标记过期。

## 3.11 Phase 1 数据流

```
用户手动输入 (Web Form)
    │
    ▼
MatchupInput 数据模型
    │
    ├──→ 转为自然语言文本
    │         │
    │         ▼
    │   graph_builder（复用）
    │   创建临时 Zep 图谱 + NBA 固定本体 + 注入文本
    │         │
    │         ▼
    │   zep_tools.quick_search()（复用）
    │   从图谱检索相关事实
    │         │
    │         ▼
    │     graph_context
    │         │
    └─────────┤
              ▼
      DebateEngine（新建）
      3轮 × 6个分析师，每次调用 llm_client.chat_json()
              │
              ▼
        DebateResult
              │
              ▼
    PredictionGenerator（新建）
    投票汇总 + 置信度加权 + edge 计算
              │
              ▼
      PredictionOutput（L1/L2/L3）
              │
              ▼
       API JSON 响应（支持 ?level=L1）
```

## 3.8 Phase 1 图谱策略

MVP 阶段每次预测创建临时图谱，用完删除，节省 Zep 免费额度。Phase 2 改为持久化图谱。

---

# 四、Phase 2 — 数据接入 + Chrome 插件

> 目标：自动化数据获取，实现 Polymarket 数据闭环，推出 Chrome 插件。

## Phase 2 覆盖的改动项

**#3 数据源改造、#6 记忆更新改造、#7 Polymarket 数据闭环、#9 Chrome 插件**

## 4.1 数据源改造（#3）

**现状**：用户上传 PDF/MD/TXT → `file_parser.py` 提取文本。

**改为**：新建 `data_fetcher` 服务，自动从 API 拉取结构化 NBA 数据：

| 数据类型 | 来源 | 频率 |
|---------|------|------|
| 球队/球员基础信息 | NBA Stats API / Basketball Reference | 赛季初一次，有变动更新 |
| 赛季数据（场均、排名） | NBA Stats API | 每日更新 |
| 伤病报告 | ESPN / Official NBA Injury Report | 赛前更新 |
| 历史对战记录 | Basketball Reference | 按需 |

数据拉回后转为文本描述，通过现有 `graph_builder.add_text_batches()` 注入 Zep 图谱，或直接以结构化 episode 写入。

此阶段图谱改为**持久化**——不再每次删除，而是持续积累。需要一个定期更新策略（每日增量更新，而非全量重建）。

## 4.2 Polymarket 数据闭环（#7）

**赛前**：自动拉取 Polymarket 当前赔率，作为分析师 Agent 的输入之一（Agent 可以说"市场定价偏高/偏低"）。

Polymarket 有基于 Polygon/CLOB 的公开 API，可直接对接。也可以通过 Chrome 插件从页面 DOM 抓取（更简单，不用处理 API 认证）。

**赛后**：拉取比赛结果，更新图谱，计算本次预测的准确率。结果反馈到 Phase 3 的回测系统。

## 4.3 记忆更新改造（#6）

**现状**：`zep_graph_memory_updater.py` 将社媒行为（发帖、点赞、转发）转为自然语言写入图谱。

**改为**：写入的内容变成比赛结果和数据更新：
- 比赛结果：`"76人 112-105 击败 热火，2026-03-28"`
- 球员表现：`"Embiid 32分11篮板，投篮 12/22"`
- 伤病变动：`"Embiid 列为 questionable，膝伤"`
- 赔率变动：`"PHI 胜负线 24h 内从 55¢ 变到 58¢"`

图谱的时间维度（Zep edge 的 `valid_at` / `invalid_at`）在此特别有用，可追踪球员状态随时间变化。

## 4.4 Chrome 插件（#9）

**功能 1 — 读取页面数据**：
- content script 从 Polymarket NBA 页面 DOM 中提取对阵信息、赔率、order book 等
- 发送到后端 `POST /api/prediction/create`（同 MVP 接口，多传 `source: "chrome_extension"` 和 `source_url`）

**功能 2 — 展示预测结果**：
- popup 中展示 L1 预测卡片（调用 `GET /api/prediction/result/{id}?level=L1`）
- 点击跳转 Web 详情页看 L2 + L3

**后端无需改动**——Phase 1 的 API 已经为插件预留了 `?level=L1` 和 `source` 字段。

## 4.5 Phase 2 新增模块

```
backend/app/services/
├── data_fetcher/
│   ├── nba_stats.py        # NBA Stats API 数据拉取
│   ├── injury_report.py    # 伤病报告拉取
│   └── polymarket.py       # Polymarket 赔率拉取和结算

chrome-extension/           # 新目录，独立于现有前后端
├── manifest.json
├── content.js              # Polymarket 页面数据提取
├── popup.html / popup.js   # 预测卡片展示
└── background.js
```

## 4.6 Phase 2 对图谱架构的影响

- 图谱从"临时创建用完删除"变为"持久化累积"
- 需要一个**更新调度策略**：每日拉取数据 → 增量写入图谱 → 旧数据通过 Zep 的 `invalid_at` 标记过期
- `zep_graph_memory_updater.py` 的核心逻辑（后台线程 + 批量写入 + 重试）可以复用，只需改写 `AgentActivity` → `NBADataUpdate` 的数据结构

---

# 五、Phase 3 — 可信度 + 扩展

> 目标：让预测从"能用"变成"可信"，并为足球扩展预留架构。

## Phase 3 覆盖的改动项

**#10 回测与校准、#11 运动类型抽象**

## 5.1 回测与校准系统（#10）

**这是让产品从"玩具"变成"工具"的关键。**

**功能：**
- 记录每次预测的完整输入、输出、和最终比赛结果
- 追踪整体准确率（胜负/让分/总分各自的准确率）
- 追踪每个分析师角色的准确率（哪个 Agent 最准？）
- 根据历史表现动态调整分析师权重（准的 Agent 在汇总投票时话语权更大）
- 支持用历史数据批量回测：输入过去 N 场比赛的赛前数据，跑预测，对比实际结果

**需要的存储**：SQLite 或 PostgreSQL，记录：
- 每次预测的输入（matchup_id, teams, market data）
- 每次预测的输出（betting_card, debate_result）
- 实际比赛结果（赛后填入）
- 每个 Agent 每次的预测 vs 实际（用于计算 Agent 级别的准确率）

**对现有模块的影响**：
- `PredictionGenerator` 的汇总逻辑需支持加权投票（当前是简单多数投票）
- 权重来自 Agent 的历史准确率
- 新增 `backtester` 服务

## 5.2 运动类型抽象层（#11）

**目的**：让未来支持足球时不需要大幅重构。

**抽象方式**：

```
SportConfig 基类
├── entity_types       # 本体实体类型
├── edge_types         # 本体关系类型  
├── analyst_roles      # 分析师角色列表
├── markets            # 预测市场类型（胜负/让分/总分 vs 胜平负/角球/...）
├── data_sources       # 数据来源配置
└── prediction_markets # 对接的预测市场平台

NBAConfig(SportConfig)      # NBA 配置
FootballConfig(SportConfig) # 足球配置（未来）
```

足球需要的差异点：
- 本体不同：Club, League, MatchWeek, Referee 等
- 分析师不同：足球有"联赛强度分析师"、"主客场旅途分析师"等
- 市场不同：足球是胜平负三选一（不是二选一）
- 数据源不同：API-Football / Transfermarkt 等

**Phase 3 只需做抽象层重构 + NBAConfig 迁移，不实现 FootballConfig。** 等真正有足球需求时再写。

## 5.3 Phase 3 新增模块

```
backend/app/
├── services/
│   ├── backtester.py           # 回测引擎
│   ├── accuracy_tracker.py     # 准确率追踪和 Agent 权重计算
│   └── sport_config/
│       ├── base.py             # SportConfig 基类
│       └── nba.py              # NBAConfig（从现有硬编码迁移）
├── models/
│   └── prediction_record.py    # 预测历史记录（数据库模型）
```

---

# 六、架构设计

## 6.1 改造原则

**清理式改造。** 项目将来可能开源，需要保持代码库干净。NBA 预测流程中用不到的原有代码全部删除，不留无用模块。保留的仅限于 NBA 流程实际复用的模块。

## 6.2 复用的现有模块（仅以下模块保留）

| 模块 | 复用方式 | 涉及阶段 |
|------|---------|---------|
| `graph_builder.py` | 调用 `create_graph()`、`set_ontology()`、`add_text_batches()`、`_wait_for_episodes()` | Phase 1-2 |
| `text_processor.py` | 调用 `split_text()` 分块文本 | Phase 1-2 |
| `zep_tools.py` | 调用 `quick_search()`（Phase 1）和 `insight_forge()`（Phase 2，数据丰富后） | Phase 1-3 |
| `zep_entity_reader.py` | 过滤实体节点 | Phase 2 |
| `zep_graph_memory_updater.py` | 复用后台线程 + 批量写入的架构，改写数据结构 | Phase 1-3 |
| `llm_client.py` | `chat_json()` 给辩论引擎用，`chat()` 给关键因素生成用 | Phase 1-3 |
| `task.py` (`TaskManager`) | 管理异步预测任务的进度和状态 | Phase 1-3 |
| `config.py` | 读取 API Key 及新增配置项（清理掉 OASIS 相关配置） | Phase 1-3 |
| `logger.py`、`retry.py`、`zep_paging.py` | 原样复用 | 全部 |

## 6.3 删除的模块

以下模块在 NBA 预测流程中无用，Phase 1 开发时直接删除：

| 模块 | 原用途 | 删除理由 |
|------|--------|---------|
| `ontology_generator.py` | LLM 动态生成本体 | 改用固定 NBA 本体 |
| `oasis_profile_generator.py` | 生成社媒用户人设 | 改用预定义分析师角色 |
| `simulation_runner.py` | OASIS 模拟运行器 | 改用辩论引擎 |
| `simulation_ipc.py` | OASIS 进程间通信 | 不再需要子进程 |
| `simulation_config_generator.py` | 模拟配置生成 | 不再需要 |
| `report_agent.py` | ReACT 长篇报告生成 | 改用预测结果生成器 |
| `file_parser.py` | PDF/MD/TXT 文件解析 | 不再需要用户上传文件 |
| `api/simulation.py` | 模拟 API 路由 | 不再需要 |
| `api/report.py` | 报告 API 路由 | 不再需要 |
| `api/graph.py` | 图谱构建 API（文件上传流程） | 改为内部调用，不再暴露为用户 API |
| `models/project.py` | 项目持久化 | 不再有"项目"概念 |
| `frontend/src/components/Step1~Step5` | 原五步流程组件 | 替换为预测页面 |
| `frontend/src/views/SimulationView.vue` 等 | 原模拟/报告页面 | 替换为预测页面 |
| `scripts/run_*_simulation.py` | 模拟启动脚本 | 不再需要 |

## 6.4 API 设计

新增蓝图 `/api/prediction`，与现有的 `/api/graph`、`/api/simulation`、`/api/report` 并行。

| 方法 | 路径 | 说明 | 阶段 |
|------|------|------|------|
| POST | `/api/prediction/create` | 提交对阵数据，创建预测任务 | Phase 1 |
| GET | `/api/prediction/task/{task_id}` | 查询任务进度 | Phase 1 |
| GET | `/api/prediction/result/{matchup_id}?level=L1/L2/L3` | 获取预测结果（分层） | Phase 1 |
| GET | `/api/prediction/history` | 查看历史预测列表 | Phase 3 |
| GET | `/api/prediction/accuracy` | 查看各 Agent 准确率 | Phase 3 |
| POST | `/api/prediction/settle/{matchup_id}` | 赛后录入结果结算 | Phase 2-3 |

任务模式沿用现有的 `create_task → 轮询 task_id → 拉取 result` 模式。

## 6.5 数据模型

**MatchupInput**（Phase 1）：用户提交的比赛数据
- 主客队信息（名称、缩写）
- Polymarket 市场数据（胜负线、让分盘、总分盘的概率和盘口值）
- 补充信息、来源（manual / chrome_extension）、source_url
- 提供 `to_graph_text()` 方法将结构化数据转为自然语言文本喂给 Zep

**DebateResult**（Phase 1）：辩论引擎输出
- 3 轮 × 6 个 Agent 的预测（pick / confidence / reasoning）

**PredictionOutput**（Phase 1）：最终预测结果
- L1 betting_card：3 个市场的投注建议
- L2 key_factors + consensus
- L3 完整辩论记录

**PredictionRecord**（Phase 3）：持久化历史记录
- 输入快照、输出快照、实际结果、准确率

## 6.6 图谱策略

从 Phase 1 起使用**持久化图谱**。按赛季维护一个主图谱（NBA 固定本体），通过 `data_fetcher` 每日增量写入球队/球员/伤病数据，通过改造后的 `memory_updater` 写入比赛结果。预测时直接从主图谱检索上下文。旧数据通过 Zep 的 `invalid_at` / `expired_at` 标记过期。

## 6.7 前端架构

**Phase 1**：删除原有的 Step1~Step5 组件和 SimulationView、ReportView 等页面，替换为 `/predict` 预测页面（输入 → 进度 → 结果）。

**Phase 2**：新增 `/predict/result/{matchup_id}` 详情页（Chrome 插件跳转目标），以及 Chrome 插件独立目录。

**Phase 3**：新增 `/predict/history` 历史记录页 和 `/predict/accuracy` 准确率仪表盘。

## 6.8 文件变动总览

### 新增文件

| 文件 | 说明 | 阶段 |
|------|------|------|
| `backend/app/services/nba_ontology.py` | NBA 固定本体定义 | Phase 1 |
| `backend/app/models/matchup.py` | 比赛输入数据模型 | Phase 1 |
| `backend/app/services/analyst_agents.py` | 6 个分析师角色定义 | Phase 1 |
| `backend/app/services/debate_engine.py` | 多轮辩论引擎 | Phase 1 |
| `backend/app/services/prediction_generator.py` | 预测结果汇总 | Phase 1 |
| `backend/app/api/prediction.py` | 预测 API 路由 | Phase 1 |
| `backend/app/services/data_fetcher/` | NBA Stats API 数据拉取、伤病报告拉取 | Phase 1 |
| `frontend/src/views/PredictionView.vue` | 预测主页面 | Phase 1 |
| `frontend/src/api/prediction.js` | 前端 API 调用 | Phase 1 |
| `chrome-extension/` | Chrome 插件 | Phase 2 |
| `backend/app/services/polymarket_client.py` | （可选）Polymarket API 对接 | Phase 2 |
| `backend/app/services/backtester.py` | 回测引擎 | Phase 3 |
| `backend/app/services/accuracy_tracker.py` | 准确率追踪 | Phase 3 |
| `backend/app/services/sport_config/` | 运动类型抽象层 | Phase 3 |
| `backend/app/models/prediction_record.py` | 预测历史记录模型 | Phase 3 |

### 修改文件（Phase 1）

| 文件 | 改动 |
|------|------|
| `backend/app/config.py` | 追加辩论引擎配置项，删除 OASIS 模拟相关配置 |
| `backend/app/api/__init__.py` | 删除 `simulation_bp`、`report_bp`、`graph_bp`，新增 `prediction_bp` |
| `backend/app/__init__.py` | 注册 `prediction_bp`，删除旧蓝图注册和 OASIS 清理函数 |
| `frontend/src/router/index.js` | 删除原有路由，替换为 `/predict` 路由 |
| `.env.example` | 追加新配置项说明，删除 OASIS 相关说明 |

---

# 七、关键设计决策

## 7.1 为什么用辩论而不是社媒模拟？

社媒模拟（OASIS）的输出是"张三转发了李四的帖子"——这对预测没有信息量。辩论的输出是结构化 JSON（pick + confidence + reasoning），可以直接汇总为投注建议。而且辩论引擎比 OASIS 简单一个数量级：无需子进程、IPC、双平台并行。

## 7.2 为什么 Agent 要有认知偏差？

如果 6 个 Agent 都是"客观中立"的，它们会给出几乎相同的结论——那就和只用一个 Agent 没区别了。**偏差导致分歧，分歧才有信息量**。当 5 个 Agent 选 A 但"投注专家"坚持选 B 并给出合理理由时，这个分歧本身就是有价值的信号。

## 7.3 为什么 Edge 计算这么简单？

`edge = 模型概率 - 市场概率`。MVP 阶段故意保持简单——复杂的 Kelly Criterion、EV 计算等可以在 Phase 3 引入。简单的 edge 足以帮用户判断"这场值不值得下"。

## 7.4 为什么 Phase 1 就要持久化图谱？

Phase 1 已经接入 NBA Stats API 拉取球队/球员/伤病等数据，数据会持续积累。使用持久化图谱有三个好处：
1. 分析师 Agent 在辩论时能检索到丰富的历史数据（近期战绩、历史对战、伤病记录），而不只是用户手动输入的信息
2. 赛后比赛结果写回图谱，下次预测同一支球队时自动拥有更新的上下文
3. Zep 的时间维度（`valid_at` / `invalid_at`）天然适合追踪"球员 X 在某段时间内的状态变化"

## 7.5 为什么 Chrome 插件放在 Phase 2 而不是 Phase 1？

MVP 需要尽快验证核心假设（辩论式预测是否有效）。Chrome 插件是用户体验优化，不是核心逻辑。但 Phase 1 的 API 设计已经为插件预留了所有接口（`?level=L1`、`source` 字段）。
