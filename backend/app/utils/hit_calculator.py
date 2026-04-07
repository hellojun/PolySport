"""
预测命中状态计算工具
"""

import re


def compute_hit_status(prediction: dict, game_result: dict) -> dict:
    """
    计算预测命中状态。
    betting_card 是客队视角 (左=客队, 右=主队):
      - moneyline: pick=客队缩写, model_probability=客队胜概率
      - spread: pick="客队 +/-线", model_probability=客队 cover 概率
      - total: pick="OVER 线", model_probability=OVER 概率
    """
    betting_card = prediction.get('betting_card', [])
    home_score = game_result.get('home_score')
    away_score = game_result.get('away_score')

    if home_score is None or away_score is None:
        return {"moneyline_hit": None, "spread_hit": None, "total_hit": None,
                "hit_count": 0, "total_markets": 0}

    result = {"moneyline_hit": None, "spread_hit": None, "total_hit": None}
    hit_count = 0
    total_markets = 0

    for card in betting_card:
        market = card.get('market', '')
        pick = card.get('pick', '')
        model_prob = card.get('model_probability', 0.5)

        if market == 'moneyline':
            total_markets += 1
            # model_probability = 客队胜概率; > 0.5 → 选客队
            model_picks_away = model_prob > 0.5
            away_won = away_score > home_score
            if home_score == away_score:
                result["moneyline_hit"] = "push"
                hit_count += 1
            else:
                result["moneyline_hit"] = model_picks_away == away_won
                if result["moneyline_hit"]:
                    hit_count += 1

        elif market == 'spread':
            total_markets += 1
            # spread pick 格式: "客队 +3.5" 或 "客队 -3.5"
            # model_probability = 客队 cover 概率
            m = re.search(r'([+-]?\d+\.?\d*)', pick)
            if m:
                spread_line = float(m.group(1))  # 客队视角的让分线
                away_margin = away_score - home_score
                covered = (away_margin + spread_line) > 0
                model_picks_cover = model_prob > 0.5
                if (away_margin + spread_line) == 0:
                    result["spread_hit"] = "push"
                    hit_count += 1
                else:
                    result["spread_hit"] = model_picks_cover == covered
                    if result["spread_hit"]:
                        hit_count += 1

        elif market == 'total':
            total_markets += 1
            m = re.search(r'(\d+\.?\d*)', pick)
            if m:
                total_line = float(m.group(1))
                actual_total = home_score + away_score
                is_over = actual_total > total_line
                model_picks_over = model_prob > 0.5
                if actual_total == total_line:
                    result["total_hit"] = "push"
                    hit_count += 1
                else:
                    result["total_hit"] = model_picks_over == is_over
                    if result["total_hit"]:
                        hit_count += 1

    result["hit_count"] = hit_count
    result["total_markets"] = total_markets
    return result


def normalize_hit_status(hs: dict) -> dict:
    """
    根据个别市场的 hit 值重新计算 hit_count/total_markets。
    修复旧缓存中 push 未计入 hit_count 的问题。
    """
    if not hs:
        return hs
    hit_count = 0
    total_markets = 0
    for key in ("moneyline_hit", "spread_hit", "total_hit"):
        val = hs.get(key)
        if val is not None:
            total_markets += 1
            if val is True or val == "push":
                hit_count += 1
    hs["hit_count"] = hit_count
    hs["total_markets"] = total_markets
    return hs
