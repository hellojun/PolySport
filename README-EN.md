<div align="center">

# PolySport

**Multi-Agent Debate × Knowledge Graph × On-Chain Smart Money — AI Sports Prediction Engine**

[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## ⚡ Overview

**PolySport** is an AI sports prediction engine powered by multi-agent debate. The system employs 7 AI analysts with distinct cognitive biases, conducting 3 rounds of debate (21 LLM calls total), combined with knowledge graph and on-chain smart money data, to generate predictions across moneyline, spread, and total markets.

> **Core Flow**: Select game → Data collection → Knowledge graph → AI debate → Generate prediction

### Key Features

- **Multi-Agent Debate**: 7 analysts (stats, betting, injury, tactical, momentum, home court, smart money), each with independent cognitive biases, reaching weighted consensus through 3 rounds of debate
- **Knowledge Graph**: NBA ontology graph built on Zep (10 entity types, 8 relation types), providing structured context for debate
- **On-Chain Smart Money**: Tracks Polymarket whale positions to quantify informed conviction
- **Layered Output**: L1 betting card / L2 key factors & consensus / L3 full debate log

## 🔄 Workflow

```
01 Data Collection    NBA Stats API + Polymarket odds + on-chain smart money
         ↓
02 Knowledge Graph    Zep GraphRAG builds NBA ontology (teams/players/injuries/matchups)
         ↓
03 AI Debate          7 analysts × 3 rounds = 21 LLM calls
         ↓
04 Generate Prediction    Weighted consensus → ML / Spread / Total
```

## 🏗️ Architecture

| Layer | Stack |
|-------|-------|
| Frontend | Vue 3 + Vite + vue-i18n |
| Backend | Flask + SQLAlchemy + PostgreSQL |
| Cache | Redis |
| Graph | Zep Cloud (GraphRAG) |
| LLM | Any OpenAI SDK-compatible LLM API |
| Data | NBA Stats API + Polymarket + Polygon RPC |

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| **Node.js** | 18+ | `node -v` |
| **Python** | ≥3.11, ≤3.12 | `python --version` |
| **PostgreSQL** | 14+ | `psql --version` |
| **Redis** | 6+ | `redis-cli ping` |

### 1. Configure Environment

```bash
cp .env.example .env
```

**Required variables:**

```env
# LLM API (OpenAI SDK compatible)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_MODEL_NAME=your-model

# Zep Cloud (Knowledge Graph)
ZEP_API_KEY=your_zep_api_key

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/polysport

# Redis
REDIS_URL=redis://localhost:6379/0
```

### 2. Install Dependencies

```bash
# One-click install
npm run setup:all
```

Or step by step:

```bash
npm run setup          # Node deps (root + frontend)
npm run setup:backend  # Python deps (auto-creates venv)
```

### 3. Start Services

```bash
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

### Docker Deployment

```bash
cp .env.example .env
docker compose up -d
```

## 📄 License

MIT
