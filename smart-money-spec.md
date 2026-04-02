# 聪明钱分析模块 — 产品改动文档

---

## 1. 背景

Polymarket 运行在 Polygon 链上，所有交易公开可查。存在一批在体育赛道长期盈利的"聪明钱"地址（高胜率、盈利分散、非套利机器人）。追踪这些地址在某场 NBA 比赛上的持仓方向，是一个有价值的预测信号。

当前系统有 6 个分析师角色参与辩论。本次改动新增第 7 个——"聪明钱分析师"，以及支撑它的链上数据拉取模块。

## 2. 功能描述

### 2.1 用户视角

用户**无需额外操作**。提交预测时，系统自动：
1. 查询该场比赛对应的 Polymarket 市场中，聪明钱地址的持仓情况
2. 将聪明钱数据作为第 7 个分析师的专属输入
3. 聪明钱分析师和其他 6 个分析师一起参与 3 轮辩论

在预测结果中，用户可以看到：
- L1 预测卡片：聪明钱分析师的投票纳入了最终汇总
- L2 关键因素：可能出现如"[聪明钱分析师] 3 个体育赛道聪明钱地址重仓主队，建仓时间早于赛前 8 小时"
- L3 完整辩论：可以看到聪明钱分析师每轮的完整推理

### 2.2 聪明钱数据获取

需要一个新的数据服务，对每场比赛获取以下信息：

**输入**：Polymarket 该场比赛的 condition_id 或 market slug（可以从现有 `PolymarketService` 获取的 event 数据中提取）

**输出**：

```
{
  "market_slug": "nba-phi-mia-2026-03-30",
  "tracked_wallets": 5,           // 跟踪的聪明钱地址数
  "wallets_with_position": 3,     // 有持仓的地址数
  "majority_direction": "PHI",    // 多数方向
  "positions": [
    {
      "address": "0x63d4...",
      "alias": "wokerjoesleeper",  // 已知别名（如有）
      "direction": "PHI",           // 押哪边
      "size_usd": 5000,             // 仓位大小（美元）
      "avg_entry_price": 0.55,      // 平均建仓价
      "current_price": 0.58,        // 当前市场价
      "entry_time": "2026-03-29T14:00:00Z",  // 建仓时间
      "hours_before_game": 17,      // 距开赛小时数
      "has_hedge": false,           // 是否有对冲持仓
    },
    ...
  ],
  "summary": {
    "total_smart_money_usd": 12000,     // 聪明钱总持仓
    "direction_split": {"PHI": 2, "MIA": 1},  // 方向分布
    "avg_hours_before_game": 14,        // 平均建仓提前时间
    "early_movers": 2,                  // 提前 12h+ 建仓的数量（信号更强）
    "late_movers": 1,                   // 4h 内建仓的数量（可能在追消息）
  }
}
```

### 2.3 聪明钱地址列表

系统维护一份**体育赛道聪明钱地址配置**，初始列表来源于公开研究（如 BiteyeCN 整理的 26 个地址中的体育赛道部分）：

```
SPORT_SMART_MONEY_ADDRESSES = [
    {
        "address": "0x176a4a04be14f4f46784e2f6febd4a5b77e08d08172aa1e51dface0f20b70f9a",
        "alias": "体育赛道#1",
        "track": "sports",
        "notes": "UFC/MLB 为主，总交易量超 $7400万，平均单笔 $1.6万"
    },
    {
        "address": "0x07921379f7b31ef93da634b688b2fe36897db778",
        "alias": "ewelmealt",
        "track": "soccer",
        "notes": "Soccer 为主，19天内67个市场盈利$86万，从不中途卖出"
    },
    {
        "address": "0x6c743aafd813475986dcd930f380a1f50901bd4e",
        "alias": "middleoftheocean",
        "track": "sports",
        "notes": "足球赛道胜率83.1%，总盈利$47万，不碰冷门"
    },
    // ... 更多地址
]
```

该列表应作为配置存储，方便随时增删地址。可以是 Python 文件中的常量、JSON 配置文件、或环境变量（由实现者决定最合适的方式）。

### 2.4 聪明钱分析师角色

新增第 7 个分析师，加入现有的 `ANALYST_ROLES` 列表。该角色的特点：

- **关注领域**：链上聪明钱持仓方向、建仓时间、仓位占比、是否对冲
- **分析逻辑**：
  - 多数聪明钱押同一方向 → 信号较强
  - 建仓时间越早（赛前 12h+）→ 信号越强（说明是基于独立判断，而非追新闻）
  - 建仓时间很晚（赛前 4h 内）→ 信号较弱（可能在追消息，价格已消化）
  - 有对冲持仓的地址 → 忽略（可能是套利）
  - 仓位越大 → 信号越强
- **认知偏差**：过度信赖链上数据，可能忽略聪明钱尚未获知的信息（如临赛前的伤病变动）

该分析师的 system prompt 除了通用的对阵数据和图谱上下文外，还需要额外注入**聪明钱持仓数据**（2.2 中描述的 JSON 输出转成的自然语言文本）。

### 2.5 数据获取方式

Polymarket 的持仓数据可以通过以下方式获取（由实现者选择最可行的方案）：

**方案 A — CLOB API**：Polymarket 有公开的 CLOB API，可以查询指定地址在指定市场的持仓。不需要 API Key，但需要知道 market 的 condition_id/token_id。

**方案 B — Polygon 链上查询**：直接查询 Polygon 链上的 ERC-1155 代币持仓（Polymarket 的 outcome token 是 ERC-1155）。需要 Polygon RPC endpoint（Alchemy/Infura 免费额度即可）。

**方案 C — 第三方工具 API**：如 Polymarket Analytics 等工具可能提供聪明钱持仓的聚合数据。

如果以上方案在开发时都不可行（API 变动、限流等），可以降级为**模拟数据模式**：聪明钱分析师仍然参与辩论，但其输入标注为"链上数据暂不可用，基于市场赔率和交易量推测聪明钱行为"。确保系统在没有链上数据时也能正常运行。

## 3. 对现有代码的影响

### 3.1 新建文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/data_fetcher/smart_money.py` | 聪明钱链上数据拉取服务 |

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `backend/app/services/analyst_agents.py` | 在 `ANALYST_ROLES` 列表末尾追加第 7 个角色 |
| `backend/app/services/data_fetcher/__init__.py` | 导出新的 `SmartMoneyService` |
| `backend/app/api/prediction.py` | 在 `_prediction_worker` 的 Step 02（拉取数据）中增加聪明钱数据拉取步骤 |
| `backend/app/models/matchup.py` | `MatchupInput` 增加 `smart_money_data` 字段 |
| `backend/app/config.py` | 追加聪明钱相关配置项（如是否启用、RPC endpoint） |

### 3.3 不需要修改的文件

- `debate_engine.py` — 它调用 `get_analyst_roles()` 获取角色列表，新增角色后自动参与辩论，不需要改引擎代码
- `prediction_generator.py` — 汇总投票逻辑已经是遍历所有分析师的，新增一个自动纳入
- `nba_ontology.py` — 聪明钱数据不需要新的实体类型
- 前端文件 — 不需要改动，结果展示已经是动态遍历分析师列表

## 4. 数据流

```
现有流程（不变）：
  用户输入 → NBA Stats 拉取 → Polymarket 赔率 → 构建图谱 → 辩论 → 预测

新增的数据流：
  Polymarket event data（已有）
      │
      ├── 提取 condition_id / token_id
      │
      ▼
  SmartMoneyService.fetch_positions(condition_id, addresses)
      │
      ├── 查询每个聪明钱地址的持仓
      ├── 过滤有对冲的地址
      ├── 计算 summary（方向分布、平均建仓时间等）
      │
      ▼
  smart_money_context（自然语言文本）
      │
      ▼
  注入到聪明钱分析师的 prompt（作为额外 context）
```

注意：聪明钱数据**不需要写入 Zep 图谱**。它是实时数据，只需要在辩论时作为 prompt 的一部分传给聪明钱分析师即可。

## 5. 聪明钱数据传递给分析师的方式

当前 `build_analyst_prompt()` 接收 `matchup_text` 和 `graph_context` 两个文本参数。

聪明钱分析师需要一个额外的参数。建议的方式：

在 `build_analyst_prompt()` 增加一个可选参数 `extra_context: Optional[str] = None`，仅当 `role.id == "smart_money_analyst"` 时传入聪明钱数据文本。其他 6 个分析师不受影响。

或者，把聪明钱数据拼入 `matchup_text`，让所有分析师都能看到（但只有聪明钱分析师的 prompt 要求他重点分析这部分数据）。由实现者判断哪种方式更合理。

## 6. 配置项

在 `Config` 中追加：

```
# 聪明钱功能
SMART_MONEY_ENABLED        是否启用聪明钱数据拉取（默认 true）
SMART_MONEY_RPC_URL         Polygon RPC endpoint（如果用方案 B）
SMART_MONEY_TIMEOUT         请求超时秒数
```

在 `.env.example` 中追加对应说明。

## 7. 降级策略

聪明钱数据拉取可能失败（API 不可用、地址没有该场持仓等）。处理方式：

- **拉取失败**：聪明钱分析师仍参与辩论，其 prompt 中注明"链上数据暂不可用"，该分析师基于市场赔率和交易量做推测
- **所有地址均无持仓**：prompt 中注明"目前没有跟踪的聪明钱地址在该市场有持仓"，这本身也是信号（聪明钱可能认为这场没有价值）
- **整个功能关闭**（`SMART_MONEY_ENABLED=false`）：不拉取数据，不加载聪明钱分析师角色，辩论回退到 6 个分析师
