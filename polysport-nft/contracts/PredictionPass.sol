// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

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
