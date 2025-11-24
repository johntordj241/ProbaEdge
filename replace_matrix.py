from pathlib import Path
from textwrap import dedent
path = Path('utils/predictions.py')
text = path.read_text(encoding='utf-8')
needle = 'def _markets_from_matrix('
start = text.index(needle)
end = text.index('\n\ndef _betting_tips', start)
new_block = dedent('''
    def _markets_from_matrix(
        matrix: Optional[List[List[float]]],
        current_home: int,
        current_away: int,
    ) -> Dict[str, float]:
        def _baseline() -> Dict[str, float]:
            total_goals = current_home + current_away
            base = {
                "home": 1.0 if current_home > current_away else 0.0,
                "draw": 1.0 if current_home == current_away else 0.0,
                "away": 1.0 if current_home < current_away else 0.0,
                "over_0_5": 1.0 if total_goals >= 1 else 0.0,
                "over_1_5": 1.0 if total_goals >= 2 else 0.0,
                "over_2_5": 1.0 if total_goals >= 3 else 0.0,
                "over_3_5": 1.0 if total_goals >= 4 else 0.0,
                "btts_yes": 1.0 if (current_home > 0 and current_away > 0) else 0.0,
                "home_over_1_5": 1.0 if current_home >= 2 else 0.0,
                "away_over_1_5": 1.0 if current_away >= 2 else 0.0,
                "home_win_by_2": 1.0 if (current_home - current_away) >= 2 else 0.0,
                "away_win_by_2": 1.0 if (current_away - current_home) >= 2 else 0.0,
                "btts_yes_over_2_5": 1.0 if (current_home > 0 and current_away > 0 and total_goals >= 3) else 0.0,
            }
            base["under_0_5"] = 1.0 - base["over_0_5"]
            base["under_1_5"] = 1.0 - base["over_1_5"]
            base["under_2_5"] = 1.0 - base["over_2_5"]
            base["under_3_5"] = 1.0 - base["over_3_5"]
            base["btts_no"] = 1.0 - base["btts_yes"]
            base["ht_home"] = base["home"]
            base["ht_draw"] = base["draw"]
            base["ht_away"] = base["away"]
            for combo in ["1/1", "1/N", "1/2", "N/1", "N/N", "N/2", "2/1", "2/N", "2/2"]:
                base[f"htft_{combo}"] = 1.0 if combo == "1/1" else 0.0
            return base

        if matrix is None:
            return _baseline()

        aggregates = {
            "home": 0.0,
            "draw": 0.0,
            "away": 0.0,
            "over_0_5": 0.0,
            "over_1_5": 0.0,
            "over_2_5": 0.0,
            "over_3_5": 0.0,
            "btts_yes": 0.0,
            "home_over_1_5": 0.0,
            "away_over_1_5": 0.0,
            "home_win_by_2": 0.0,
            "away_win_by_2": 0.0,
            "btts_yes_over_2_5": 0.0,
        }
        for i, row in enumerate(matrix):
            for j, prob in enumerate(row):
                final_home = current_home + i
                final_away = current_away + j
                total_goals = final_home + final_away
                if final_home > final_away:
                    aggregates["home"] += prob
                elif final_home == final_away:
                    aggregates["draw"] += prob
                else:
                    aggregates["away"] += prob
                if total_goals >= 1:
                    aggregates["over_0_5"] += prob
                if total_goals >= 2:
                    aggregates["over_1_5"] += prob
                if total_goals >= 3:
                    aggregates["over_2_5"] += prob
                if total_goals >= 4:
                    aggregates["over_3_5"] += prob
                if final_home > 0 and final_away > 0:
                    aggregates["btts_yes"] += prob
                    if total_goals >= 3:
                        aggregates["btts_yes_over_2_5"] += prob
                if final_home >= 2:
                    aggregates["home_over_1_5"] += prob
                if final_away >= 2:
                    aggregates["away_over_1_5"] += prob
                if final_home - final_away >= 2:
                    aggregates["home_win_by_2"] += prob
                if final_away - final_home >= 2:
                    aggregates["away_win_by_2"] += prob
        aggregates["btts_no"] = 1.0 - aggregates["btts_yes"]
        aggregates["under_0_5"] = 1.0 - aggregates["over_0_5"]
        aggregates["under_1_5"] = 1.0 - aggregates["over_1_5"]
        aggregates["under_2_5"] = 1.0 - aggregates["over_2_5"]
        aggregates["under_3_5"] = 1.0 - aggregates["over_3_5"]
        aggregates["ht_home"] = aggregates["home"]
        aggregates["ht_draw"] = aggregates["draw"]
        aggregates["ht_away"] = aggregates["away"]
        for combo in ["1/1", "1/N", "1/2", "N/1", "N/N", "N/2", "2/1", "2/N", "2/2"]:
            aggregates[f"htft_{combo}"] = 0.0
        return aggregates
''')
text = text[:start] + new_block + text[end:]
path.write_text(text, encoding='utf-8')
