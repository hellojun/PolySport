<div align="center">

# PolySport

**多智能体辩论 × 知识图谱 × 链上聪明钱 — AI 体育预测引擎**

[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## ⚡ 项目概述

**PolySport** 是一款基于多智能体辩论的 AI 体育预测引擎。系统通过 7 位具有不同认知偏差的 AI 分析师，经过 3 轮辩论（共 21 次 LLM 调用），结合知识图谱与链上聪明钱数据，生成胜负、让分、总分三大市场的预测结果。

> **核心流程**：选择比赛 → 数据采集 → 知识图谱构建 → AI 辩论分析 → 生成预测

### 技术亮点

- **多智能体辩论**：7 位分析师（统计、投注、伤病、战术、状态、主场、聪明钱），各有独立认知偏差，通过 3 轮辩论达成加权共识
- **知识图谱**：基于 Zep 构建 NBA 本体图谱（10 类实体、8 类关系），为辩论提供结构化上下文
- **链上聪明钱**：追踪 Polymarket 链上大户持仓方向，量化知情资金的信心程度
- **分层输出**：L1 投注卡片 / L2 关键因素与共识度 / L3 完整辩论记录

## 🔄 工作流程

```
01 数据采集    NBA Stats API + Polymarket 盘口 + 链上聪明钱
       ↓
02 知识图谱    Zep GraphRAG 构建 NBA 本体（球队/球员/伤病/对阵）
       ↓
03 AI 辩论     7 位分析师 × 3 轮 = 21 次 LLM 调用
       ↓
04 生成预测    加权共识 → 胜负 / 让分 / 总分
```

## 🏗️ 技术架构

| 层 | 技术栈 |
|---|--------|
| 前端 | Vue 3 + Vite + vue-i18n |
| 后端 | Flask + SQLAlchemy + PostgreSQL |
| 缓存 | Redis |
| 图谱 | Zep Cloud (GraphRAG) |
| LLM | 兼容 OpenAI SDK 格式的任意 LLM API |
| 数据 | NBA Stats API + Polymarket + Polygon RPC |

## 🚀 快速开始

### 前置要求

| 工具 | 版本要求 | 安装检查 |
|------|---------|---------|
| **Node.js** | 18+ | `node -v` |
| **Python** | ≥3.11, ≤3.12 | `python --version` |
| **PostgreSQL** | 14+ | `psql --version` |
| **Redis** | 6+ | `redis-cli ping` |

### 1. 配置环境变量

```bash
cp .env.example .env
```

**必需的环境变量：**

```env
# LLM API（支持 OpenAI SDK 格式）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_MODEL_NAME=your-model

# Zep Cloud（知识图谱）
ZEP_API_KEY=your_zep_api_key

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/polysport

# Redis
REDIS_URL=redis://localhost:6379/0
```

### 2. 安装依赖

```bash
# 一键安装所有依赖
npm run setup:all
```

或分步安装：

```bash
npm run setup          # Node 依赖（根目录 + 前端）
npm run setup:backend  # Python 依赖（自动创建虚拟环境）
```

### 3. 启动服务

```bash
npm run dev
```

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`

### Docker 部署

```bash
cp .env.example .env
docker compose up -d
```

## 📄 License

MIT
