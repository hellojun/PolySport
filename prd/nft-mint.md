# 部署 PredictionPass NFT 合约到 Polygon + 准备批量 Mint 脚本

## 背景

PolySport 的 NFT 图片和 Metadata API 已经部署好了：
- 图片：https://polysport.pro/nft/pass.png
- Metadata：https://polysport.pro/api/nft/{tokenId}

现在需要：
1. 部署 ERC-721 合约到 Polygon PoS 主网
2. 准备批量 mint 脚本（目标 43,770 个地址）

## 任务 1：用 Hardhat 部署合约

### 合约代码（PredictionPass.sol）

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

contract PredictionPass is ERC721, Ownable {
    using Strings for uint256;

    uint256 private _nextTokenId;
    string private _baseTokenURI;

    mapping(address => uint256) public mintTimestamp;

    constructor(string memory baseURI)
        ERC721("PolySport Prediction Pass", "PSPP")
        Ownable(msg.sender)
    {
        _baseTokenURI = baseURI;
    }

    function batchMint(address[] calldata recipients) external onlyOwner {
        for (uint256 i = 0; i < recipients.length; i++) {
            if (balanceOf(recipients[i]) == 0) {
                uint256 tokenId = _nextTokenId++;
                _safeMint(recipients[i], tokenId);
                mintTimestamp[recipients[i]] = block.timestamp;
            }
        }
    }

    function isTrialActive(address user) external view returns (bool) {
        if (balanceOf(user) == 0) return false;
        return block.timestamp <= mintTimestamp[user] + 7 days;
    }

    function trialRemainingSeconds(address user) external view returns (uint256) {
        if (balanceOf(user) == 0) return 0;
        uint256 expiry = mintTimestamp[user] + 7 days;
        if (block.timestamp >= expiry) return 0;
        return expiry - block.timestamp;
    }

    function _baseURI() internal view override returns (string memory) {
        return _baseTokenURI;
    }

    function setBaseURI(string memory baseURI) external onlyOwner {
        _baseTokenURI = baseURI;
    }

    function totalSupply() external view returns (uint256) {
        return _nextTokenId;
    }
}
```

### Hardhat 配置要求

- Solidity 版本：0.8.20
- 网络：Polygon PoS Mainnet (chainId: 137, RPC: https://polygon-rpc.com)
- 依赖：@openzeppelin/contracts@5, hardhat, @nomicfoundation/hardhat-toolbox
- 开启 optimizer（runs: 200）
- 部署参数 baseURI：`https://polysport.pro/api/nft/`

### .env 需要

```
PRIVATE_KEY=<部署钱包的私钥，钱包里需要有 2-3 MATIC>
POLYGONSCAN_API_KEY=<可选，用于合约验证>
```

### 部署脚本要求

1. 部署合约，传入 baseURI = "https://polysport.pro/api/nft/"
2. 打印合约地址
3. 等待几个区块确认
4. 自动在 Polygonscan 上验证合约源码（如果有 API key）

## 任务 2：批量 Mint 脚本 (mint.js)

### 输入
- CSV 文件路径：`./addresses.csv`（从 Dune 导出，包含 wallet_address 和 user_tier 列）
- 按顺序 mint：先 whale（tokenId 0~17307），再 active（17308~43769）

### 逻辑
1. 读取 CSV，按 tier 排序（whale 在前）
2. 去重，过滤无效地址
3. 检查每个地址是否已 mint（调用 balanceOf）
4. 分批执行 batchMint，每批 200 个地址
5. 批次间隔 3 秒
6. 打印进度，记录失败的批次
7. 失败地址保存到 failed_addresses.csv，可重跑

### Gas 控制
- 每地址预估 gas ~30,000，加 50,000 overhead
- gasLimit = batch.length * 30000 + 50000
- 如果当前 gas price > 100 Gwei，自动暂停等待

## 文件结构

```
polysport-nft/
├── contracts/
│   └── PredictionPass.sol
├── scripts/
│   ├── deploy.ts          # 部署脚本
│   └── mint.ts            # 批量 mint 脚本
├── addresses.csv          # Dune 导出的地址（用户自己放）
├── hardhat.config.ts
├── .env
└── package.json
```

## 验证标准

- [ ] `npx hardhat run scripts/deploy.ts --network polygon` 成功部署合约
- [ ] 合约在 Polygonscan 上可查看
- [ ] `tokenURI(0)` 返回 `https://polysport.pro/api/nft/0`
- [ ] mint 脚本可以正确读取 CSV 并分批 mint
- [ ] mint 一个测试地址后，`isTrialActive(testAddr)` 返回 true

## 执行顺序

1. 先 `npm install` 安装依赖
2. 用户填写 .env 中的 PRIVATE_KEY
3. 运行 deploy 脚本部署合约
4. 记录合约地址，更新到 mint 脚本或 .env 中
5. 用户把 addresses.csv 放到项目根目录
6. 运行 mint 脚本开始空投