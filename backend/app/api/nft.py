"""
NFT Metadata API — ERC-721 标准
GET /api/nft/<token_id>
"""

from flask import jsonify
from . import nft_bp

TOTAL_SUPPLY = 43770
WHALE_CUTOFF = 17308  # 0~17307 = Whale, 17308~43769 = Active


@nft_bp.route('/<int:token_id>')
def token_metadata(token_id: int):
    if token_id < 0 or token_id >= TOTAL_SUPPLY:
        return jsonify({"error": "Token not found"}), 404

    tier = "Whale" if token_id < WHALE_CUTOFF else "Active"

    metadata = {
        "name": f"PolySport Prediction Pass #{token_id}",
        "description": (
            "PolySport Prediction Pass grants access to AI-powered NBA game predictions. "
            "Our debate engine uses 7 specialized analyst agents across 3 rounds to deliver "
            "high-accuracy forecasts."
        ),
        "image": "https://polysport.pro/nft/pass.png",
        "external_url": "https://polysport.pro/claim",
        "attributes": [
            {"trait_type": "Tier", "value": tier},
            {"trait_type": "Win Rate", "value": "92.5%"},
            {"trait_type": "Games Analyzed", "value": 128, "display_type": "number"},
            {"trait_type": "AI Agents", "value": 7, "display_type": "number"},
            {"trait_type": "Debate Rounds", "value": 3, "display_type": "number"},
            {"trait_type": "Free Trial", "value": "7 days"},
        ],
    }
    return jsonify(metadata)
