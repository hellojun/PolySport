# PolySport Prediction Pass — NFT 图片 + Metadata API 实现与部署

## 项目背景

PolySport (polysport.pro) 是一个 AI 驱动的体育预测引擎（7 个 AI 分析师多轮辩论），我们要给 Polymarket 上的 43,770 个 NBA 交易者空投一个 ERC-721 NFT（Prediction Pass），吸引他们来使用 PolySport。

NFT 合约已经部署在 Polygon 上（合约名：PredictionPass，代号：PSPP），需要实现两个东西：
1. **NFT 图片生成服务** — 动态生成 400x400 的 NFT 卡片图
2. **Metadata API** — 供钱包/OpenSea 调用的标准 ERC-721 metadata 接口

## 任务 1：NFT 图片生成

生成一张 400x400px 的 PNG 图片，作为 NFT 在钱包和 OpenSea 中的展示图。

### 设计规范（严格遵守）

**整体风格：** 深色背景 (渐变 #0a0e1a → #111827 → #0f172a)，圆角 24px
**布局从上到下：**

1. **顶部 Header**
   - 左上：小字 "AI PREDICTION ENGINE"（11px, 字间距 0.15em, 大写, #94a3b8），下方大字 "PolySport"（22px, 粗体 700, 白色）
   - 右上：绿色药丸标签 "NBA"（背景 rgba(34,197,94,0.12), 边框 rgba(34,197,94,0.25), 文字 #22c55e, 12px 粗体 600）

2. **中央主体（最重要的部分）**
   - 小字标签 "VERIFIED WIN RATE"（11px, 大写, #94a3b8）
   - 超大数字 **"92.5%"**（80px, 粗体 800, 绿色渐变 #22c55e → #16a34a → #15803d）
   - 下方三列数据：128 games | 7 agents | 3 rounds（用竖线分隔）

3. **底部栏**
   - 左：圆角标签 "7-day free pass"（深色半透明背景）
   - 右：monospace 字体 "polysport.pro"

**细节装饰：**
- 右上角有一个淡绿色光晕（radial-gradient, rgba(34,197,94,0.15)）
- 背景有极淡的点阵纹理（1px 圆点, 24px 间距, 5% 透明度）

### 技术实现

用 Node.js 的 `@napi-rs/canvas` 或 `sharp` + SVG 模板渲染为 PNG。图片应该支持动态参数（胜率、场次等），但初始版本可以先硬编码当前数据。

生成的图片上传到 IPFS（用 Pinata 或 nft.storage）或托管在 polysport.pro/nft/pass.png。

## 任务 2：Metadata API

### 接口定义

```
GET /api/nft/:tokenId
```

返回标准 ERC-721 metadata JSON：

```json
{
  "name": "PolySport Prediction Pass #0",
  "description": "7-day free access to PolySport AI-powered NBA predictions. Multi-agent debate system with 92.5% verified win rate across 128 games.",
  "image": "https://polysport.pro/nft/pass.png",
  "external_url": "https://polysport.pro/claim",
  "attributes": [
    { "trait_type": "Tier", "value": "Whale" },
    { "trait_type": "Win Rate", "value": "92.5%" },
    { "trait_type": "Games Analyzed", "value": 128, "display_type": "number" },
    { "trait_type": "AI Agents", "value": 7, "display_type": "number" },
    { "trait_type": "Debate Rounds", "value": 3, "display_type": "number" },
    { "trait_type": "Free Trial", "value": "7 days" }
  ]
}
```

### Tier 逻辑

根据 tokenId 判断用户 tier：
- tokenId 0 ~ 17307 → tier = "Whale"（前 17,308 个地址按交易量排序 mint）
- tokenId 17308 ~ 43769 → tier = "Active"

### 框架选择

如果 polysport.pro 是 Next.js 项目，放在 `app/api/nft/[tokenId]/route.ts`。
如果是其他框架，用最简单的方式实现即可（Express、Vercel Serverless 等都行）。

## 任务 3：部署

1. 图片生成 → 上传到可公开访问的 URL
2. Metadata API → 部署到 polysport.pro（或 Vercel/Railway）
3. 确保 `https://polysport.pro/api/nft/0` 返回正确的 JSON
4. 确保图片 URL 可以被 OpenSea/钱包正常加载

## 文件结构建议

```
polysport.pro/
├── app/
│   └── api/
│       └── nft/
│           └── [tokenId]/
│               └── route.ts      # Metadata API
├── scripts/
│   └── generate-nft-image.ts     # NFT 图片生成脚本
├── public/
│   └── nft/
│       └── pass.png              # 生成的 NFT 图片
```

## 验证标准

- [ ] `curl https://polysport.pro/api/nft/0` 返回合法的 ERC-721 metadata JSON
- [ ] `curl https://polysport.pro/api/nft/100` 返回 tier = "Whale"
- [ ] `curl https://polysport.pro/api/nft/20000` 返回 tier = "Active"
- [ ] metadata 中的 image URL 可以在浏览器中直接打开看到 400x400 的 NFT 卡片图
- [ ] 图片在 80px 缩略图尺寸下，"92.5%" 仍然清晰可读