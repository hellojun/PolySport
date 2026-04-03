#!/usr/bin/env python3
"""
NFT Prediction Pass — SVG → PNG 图片生成脚本

Usage:
    python backend/scripts/generate_nft_image.py
    python backend/scripts/generate_nft_image.py --win-rate 92.5 --games 128 --agents 7 --rounds 3
"""

import argparse
import os
import sys

try:
    import cairosvg
except ImportError:
    print("Error: cairosvg not installed. Run: pip install cairosvg")
    sys.exit(1)


def build_svg(win_rate: str, games: int, agents: int, rounds: int) -> str:
    """构建 400x400 NFT 卡片 SVG"""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0%" stop-color="#0a0e1a"/>
      <stop offset="50%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <linearGradient id="greenGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#3ba55d"/>
      <stop offset="100%" stop-color="#4ade80"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.85" cy="0.12" r="0.45">
      <stop offset="0%" stop-color="#22c55e" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#22c55e" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
      <circle cx="10" cy="10" r="0.6" fill="white" opacity="0.04"/>
    </pattern>
  </defs>

  <!-- 背景 -->
  <rect width="400" height="400" rx="24" ry="24" fill="url(#bg)"/>
  <rect width="400" height="400" rx="24" ry="24" fill="url(#glow)"/>
  <rect width="400" height="400" rx="24" ry="24" fill="url(#dots)"/>

  <!-- 边框 -->
  <rect x="1" y="1" width="398" height="398" rx="23" ry="23"
        fill="none" stroke="#22c55e" stroke-opacity="0.15" stroke-width="1"/>

  <!-- Header: 左对齐 -->
  <text x="36" y="52" text-anchor="start"
        font-family="monospace" font-size="11" font-weight="bold"
        fill="#6b7280" letter-spacing="2.5">AI PREDICTION ENGINE</text>

  <text x="36" y="86" text-anchor="start"
        font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="bold"
        fill="white">PolySport</text>

  <!-- NBA 药丸: 右上角 -->
  <rect x="310" y="38" width="58" height="28" rx="14" ry="14" fill="#22c55e" fill-opacity="0.15"/>
  <rect x="310" y="38" width="58" height="28" rx="14" ry="14"
        fill="none" stroke="#22c55e" stroke-opacity="0.4" stroke-width="0.8"/>
  <text x="339" y="57" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="bold"
        fill="#4ade80">NBA</text>

  <!-- 分割线 -->
  <line x1="36" y1="108" x2="364" y2="108" stroke="#1f2937" stroke-width="1"/>

  <!-- VERIFIED WIN RATE 标签 -->
  <text x="200" y="148" text-anchor="middle"
        font-family="monospace" font-size="12" font-weight="bold"
        fill="#9ca3af" letter-spacing="3">VERIFIED WIN RATE</text>

  <!-- 92.5% 大字 -->
  <text x="200" y="240" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="90" font-weight="bold"
        fill="url(#greenGrad)">{win_rate}%</text>

  <!-- 三列统计数据 -->
  <!-- 128 games -->
  <text x="100" y="285" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="bold"
        fill="white">{games}</text>
  <text x="100" y="305" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="12"
        fill="#6b7280">games</text>

  <!-- 竖线分隔 -->
  <line x1="160" y1="268" x2="160" y2="310" stroke="#2d3748" stroke-width="1"/>

  <!-- 7 agents -->
  <text x="200" y="285" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="bold"
        fill="white">{agents}</text>
  <text x="200" y="305" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="12"
        fill="#6b7280">agents</text>

  <!-- 竖线分隔 -->
  <line x1="240" y1="268" x2="240" y2="310" stroke="#2d3748" stroke-width="1"/>

  <!-- 3 rounds -->
  <text x="300" y="285" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="bold"
        fill="white">{rounds}</text>
  <text x="300" y="305" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="12"
        fill="#6b7280">rounds</text>

  <!-- 分割线 -->
  <line x1="36" y1="322" x2="364" y2="322" stroke="#1f2937" stroke-width="1"/>

  <!-- 底部: 网址居中显眼 -->
  <text x="200" y="354" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="bold"
        fill="#4ade80">polysport.pro</text>

  <!-- 7-day free pass 标签居中 -->
  <rect x="140" y="366" width="120" height="24" rx="12" ry="12"
        fill="#22c55e" fill-opacity="0.1"/>
  <rect x="140" y="366" width="120" height="24" rx="12" ry="12"
        fill="none" stroke="#22c55e" stroke-opacity="0.3" stroke-width="0.8"/>
  <text x="200" y="383" text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif" font-size="11" font-weight="bold"
        fill="#4ade80">7-day free pass</text>
</svg>'''


def main():
    parser = argparse.ArgumentParser(description="Generate NFT Prediction Pass PNG")
    parser.add_argument("--win-rate", default="92.5", help="Win rate (default: 92.5)")
    parser.add_argument("--games", type=int, default=128, help="Games analyzed (default: 128)")
    parser.add_argument("--agents", type=int, default=7, help="AI agents (default: 7)")
    parser.add_argument("--rounds", type=int, default=3, help="Debate rounds (default: 3)")
    parser.add_argument("--output", default=None, help="Output path (default: frontend/public/nft/pass.png)")
    args = parser.parse_args()

    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_path = os.path.join(project_root, "frontend", "public", "nft", "pass.png")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    svg_content = build_svg(args.win_rate, args.games, args.agents, args.rounds)
    cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), write_to=output_path,
                     output_width=400, output_height=400)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Generated: {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
