# MiroFish 项目架构流程图

## 整体架构

```mermaid
graph TB
    subgraph User["👤 用户"]
        Upload["上传文档 PDF/MD/TXT<br/>+ 输入模拟需求"]
    end

    subgraph Frontend["🖥️ 前端 (Vue 3 + Vite)"]
        Home["首页 Home.vue<br/>文件上传 & 项目创建"]
        Step1["Step1: 图谱构建<br/>GraphPanel.vue (D3.js)"]
        Step2["Step2: 环境搭建<br/>实体选择 & 配置"]
        Step3["Step3: 开始模拟<br/>实时监控面板"]
        Step4["Step4: 报告生成<br/>Markdown 渲染"]
        Step5["Step5: 深度互动<br/>对话界面"]
    end

    subgraph Backend["⚙️ 后端 (Python Flask)"]
        GraphAPI["Graph API<br/>/api/graph/*"]
        SimAPI["Simulation API<br/>/api/simulation/*"]
        ReportAPI["Report API<br/>/api/report/*"]
    end

    subgraph Services["🔧 核心服务层"]
        OntGen["OntologyGenerator<br/>本体生成"]
        GraphBuilder["GraphBuilderService<br/>图谱构建"]
        SimManager["SimulationManager<br/>模拟管理"]
        ProfileGen["OasisProfileGenerator<br/>Agent 档案生成"]
        ConfigGen["SimulationConfigGenerator<br/>模拟配置生成"]
        SimRunner["SimulationRunner<br/>模拟执行引擎"]
        ReportAgent["ReportAgent<br/>报告生成代理"]
    end

    subgraph External["☁️ 外部服务"]
        LLM["LLM API<br/>(Qwen/Claude/OpenAI)"]
        Zep["Zep Cloud<br/>知识图谱 & 记忆管理"]
        OASIS["OASIS (CAMEL-AI)<br/>社交媒体模拟框架"]
    end

    subgraph Storage["💾 文件存储"]
        Uploads["uploads/<br/>项目文件 & 模拟数据"]
    end

    Upload --> Home
    Home --> Step1 --> Step2 --> Step3 --> Step4 --> Step5

    Step1 --> GraphAPI
    Step2 --> SimAPI
    Step3 --> SimAPI
    Step4 --> ReportAPI
    Step5 --> SimAPI & ReportAPI

    GraphAPI --> OntGen & GraphBuilder
    SimAPI --> SimManager & ProfileGen & ConfigGen & SimRunner
    ReportAPI --> ReportAgent

    OntGen --> LLM
    GraphBuilder --> Zep
    ProfileGen --> LLM
    ConfigGen --> LLM
    SimRunner --> OASIS & Zep
    ReportAgent --> LLM & Zep

    GraphBuilder --> Uploads
    SimRunner --> Uploads
    ReportAgent --> Uploads
```

## 核心业务流程

```mermaid
flowchart TD
    A["📄 用户上传文档 + 模拟需求"] --> B["🧠 LLM 分析文档<br/>生成本体 (10个实体类型 + 6-10个关系类型)"]
    B --> C["🕸️ Zep Cloud 构建知识图谱<br/>文本分块 → 批量处理 → 提取实体和关系"]
    C --> D["📊 图谱可视化展示<br/>D3.js 力导向图"]

    D --> E["👥 从图谱提取实体<br/>ZepEntityReader"]
    E --> F["🎭 LLM 生成 Agent 档案<br/>Twitter 档案 (CSV) + Reddit 档案 (JSON)"]
    F --> G["⚙️ LLM 生成模拟配置<br/>轮次数 / 每轮时长 / 平台行为"]

    G --> H["🚀 启动双平台并行模拟"]

    H --> I["🐦 Twitter 模拟线程"]
    H --> J["📱 Reddit 模拟线程"]

    I --> K["Agent 执行动作<br/>发帖/点赞/转发/关注/引用"]
    J --> L["Agent 执行动作<br/>发帖/评论/点赞/踩/搜索"]

    K --> M["📝 ActionLogger 记录到 actions.jsonl"]
    L --> M
    M --> N["🧠 ZepGraphMemoryManager<br/>每轮更新图谱记忆"]
    N --> O{"是否还有剩余轮次?"}
    O -->|是| H
    O -->|否| P["✅ 模拟完成"]

    P --> Q["📋 ReportAgent 分析模拟结果<br/>ReAct 模式: 查询图谱 + 分析数据"]
    Q --> R["📄 生成 Markdown 报告<br/>分析摘要 / 关键发现 / 预测洞察"]

    R --> S["💬 深度互动"]
    S --> T["🎤 采访模拟 Agent<br/>基于 Zep 记忆的上下文对话"]
    S --> U["🤖 与 ReportAgent 对话<br/>关于报告和模拟的问答"]
```

## 数据流图

```mermaid
flowchart LR
    subgraph Input["输入"]
        Doc["文档<br/>PDF/MD/TXT"]
        Req["模拟需求"]
    end

    subgraph Process["处理"]
        direction TB
        P1["文本提取<br/>PyMuPDF"]
        P2["本体生成<br/>LLM"]
        P3["图谱构建<br/>Zep"]
        P4["Agent 生成<br/>LLM"]
        P5["模拟执行<br/>OASIS"]
        P6["报告生成<br/>ReportAgent"]
        P1 --> P2 --> P3 --> P4 --> P5 --> P6
    end

    subgraph Output["输出"]
        O1["知识图谱"]
        O2["Agent 档案<br/>CSV + JSON"]
        O3["行为日志<br/>actions.jsonl"]
        O4["预测报告<br/>Markdown"]
        O5["交互对话"]
    end

    Doc --> P1
    Req --> P2
    P3 --> O1
    P4 --> O2
    P5 --> O3
    P6 --> O4
    P6 --> O5
```

## 技术栈

```mermaid
graph LR
    subgraph FE["前端"]
        Vue3["Vue 3"]
        Vite["Vite"]
        D3["D3.js"]
        Axios["Axios"]
        VueRouter["Vue Router"]
    end

    subgraph BE["后端"]
        Flask["Flask"]
        ZepSDK["Zep SDK"]
        OpenAISDK["OpenAI SDK"]
        CamelOASIS["CAMEL-OASIS"]
        PyMuPDF["PyMuPDF"]
    end

    subgraph Infra["基础设施"]
        Docker["Docker"]
        Compose["Docker Compose"]
        UV["uv 包管理"]
        Concurrently["Concurrently"]
    end

    FE <-->|"REST API<br/>Port 3000 → 5001"| BE
    BE <-->|"API"| Cloud["Zep Cloud + LLM API"]
    Infra --> FE & BE
```

## 项目状态机

```mermaid
stateDiagram-v2
    [*] --> CREATED: 创建项目
    CREATED --> ONTOLOGY_GENERATED: LLM 生成本体
    ONTOLOGY_GENERATED --> GRAPH_BUILDING: 开始构建图谱
    GRAPH_BUILDING --> GRAPH_COMPLETED: 图谱构建完成
    GRAPH_BUILDING --> FAILED: 构建失败
    GRAPH_COMPLETED --> SIMULATION_CREATED: 创建模拟
    SIMULATION_CREATED --> PREPARING: 准备模拟环境
    PREPARING --> READY: 环境就绪
    READY --> RUNNING: 开始模拟
    RUNNING --> PAUSED: 暂停
    PAUSED --> RUNNING: 恢复
    RUNNING --> COMPLETED: 模拟完成
    RUNNING --> FAILED: 模拟失败
    COMPLETED --> REPORT_GENERATING: 生成报告
    REPORT_GENERATING --> REPORT_DONE: 报告完成
    REPORT_DONE --> INTERACTION: 深度互动
    FAILED --> [*]
    INTERACTION --> [*]
```

---

> 使用方法: 将此文件内容粘贴到 [Mermaid Live Editor](https://mermaid.live) 或任何支持 Mermaid 的 Markdown 渲染器中查看。
>
> 支持渲染的工具: GitHub、VS Code (Markdown Preview Mermaid)、Notion、Typora 等。
