"""
Analyze Over/Under 2.5 betting performance.
Calculates success rates grouped by odds ranges and odds levels.
Note: Currently no topscorer data available - analyzing Over 2.5 instead.
"""

import pandas as pd
import json
from pathlib import Path
from collections import defaultdict
import numpy as np

# Load prediction history
history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)
print(f"📊 Loaded {len(df)} predictions from history\n")

# Filter for Over/Under predictions
over_under_df = df[
    (
        df["main_pick"]
        .astype(str)
        .str.lower()
        .str.contains("over|under", na=False, case=False)
    )
    & (
        ~df["main_pick"]
        .astype(str)
        .str.lower()
        .str.contains("handicap|btts|double|victoire|score", na=False, case=False)
    )
]

if len(over_under_df) == 0:
    print("⚠️ No Over/Under predictions found in history")
    exit(1)

print(f"🎯 Found {len(over_under_df)} Over/Under 2.5 predictions\n")
print("=" * 80)

# Calculate overall stats
total = len(over_under_df)
won = len(
    over_under_df[over_under_df["result_winner"].astype(str).str.lower() == "yes"]
)
win_rate = (won / total * 100) if total > 0 else 0

print(f"\n📈 OVERALL OVER/UNDER 2.5 PERFORMANCE")
print(f"Total bets: {total}")
print(f"Won: {won}")
print(f"Lost: {total - won}")
print(f"Win rate: {win_rate:.1f}%")

# Check bet_odd column
if "bet_odd" in over_under_df.columns:
    valid_odds = pd.to_numeric(over_under_df["bet_odd"], errors="coerce")
    avg_odds = valid_odds.mean()
    print(
        f"Average odds: {avg_odds:.2f}"
        if not np.isnan(avg_odds)
        else "Average odds: N/A"
    )
else:
    print(f"Average odds: N/A")

# Group by odds ranges
print(f"\n{'=' * 80}")
print(f"\n📊 PERFORMANCE BY ODDS RANGE\n")

odds_ranges = [
    (0, 1.80, "Under 1.80"),
    (1.80, 2.0, "1.80 - 2.00"),
    (2.0, 3.0, "2.00 - 3.00"),
    (3.0, 5.0, "3.00 - 5.00"),
    (5.0, 10.0, "5.00 - 10.00"),
    (10.0, float("inf"), "10.00+"),
]

# Convert odds to numeric
over_under_df_copy = over_under_df.copy()
over_under_df_copy["bet_odd_num"] = pd.to_numeric(
    over_under_df_copy["bet_odd"], errors="coerce"
)

range_stats = []
for min_odds, max_odds, label in odds_ranges:
    mask = (over_under_df_copy["bet_odd_num"] >= min_odds) & (
        over_under_df_copy["bet_odd_num"] < max_odds
    )
    range_df = over_under_df_copy[mask]

    if len(range_df) > 0:
        range_won = len(
            range_df[range_df["result_winner"].astype(str).str.lower() == "yes"]
        )
        range_rate = range_won / len(range_df) * 100
        avg_odds = range_df["bet_odd_num"].mean()

        # Kelly expected value
        expected_value = (range_rate / 100 * avg_odds) - 1.0

        range_stats.append(
            {
                "Range": label,
                "Bets": len(range_df),
                "Won": range_won,
                "Loss": len(range_df) - range_won,
                "Win%": f"{range_rate:.1f}%",
                "Avg Odds": f"{avg_odds:.2f}",
                "EV": f"{expected_value:+.2f}",
            }
        )

        print(f"{'─' * 75}")
        print(
            f"🎲 {label:15} | Bets: {len(range_df):2} | Won: {range_won:2} | Loss: {len(range_df)-range_won:2}"
        )
        print(
            f"   Success rate: {range_rate:5.1f}% | Avg odds: {avg_odds:5.2f} | EV: {expected_value:+.2f}"
        )

# Over/Under types breakdown
print(f"\n{'=' * 80}")
print(f"\n🔍 OVER vs UNDER BREAKDOWN\n")

# Extract Over/Under from main_pick
over_df = over_under_df[
    over_under_df["main_pick"].astype(str).str.lower().str.contains("over", na=False)
]
under_df = over_under_df[
    over_under_df["main_pick"].astype(str).str.lower().str.contains("under", na=False)
]

for pick_type, pick_df in [("Over 2.5", over_df), ("Under 2.5", under_df)]:
    if len(pick_df) > 0:
        pick_won = len(
            pick_df[pick_df["result_winner"].astype(str).str.lower() == "yes"]
        )
        pick_rate = pick_won / len(pick_df) * 100
        print(
            f"{pick_type:12} | Bets: {len(pick_df):2} | Won: {pick_won:2} | Win%: {pick_rate:5.1f}%"
        )

# Monthly trends
print(f"\n{'=' * 80}")
print(f"\n📅 MONTHLY TRENDS\n")

over_under_df["date"] = pd.to_datetime(over_under_df["timestamp"], errors="coerce")
over_under_df["month"] = over_under_df["date"].dt.to_period("M")

monthly = over_under_df.groupby("month").agg(
    {
        "result_winner": lambda x: (x.astype(str).str.lower() == "yes").sum(),
        "timestamp": "count",
    }
)
monthly.columns = ["Won", "Total"]
monthly["Win%"] = (monthly["Won"] / monthly["Total"] * 100).round(1)

for month, row in monthly.iterrows():
    trend = "📈" if row["Win%"] >= 50 else "📉"
    print(
        f"{trend} {month} | Total: {int(row['Total']):2} | Won: {int(row['Won']):2} | Win%: {row['Win%']:5.1f}%"
    )

print(f"\n{'=' * 80}\n")

# Recommendations
print("💡 RECOMMENDATIONS FOR OVER/UNDER 2.5:\n")

print("1. Best Odds Range:")
best_range_idx = None
best_wr = 0
for idx, (min_o, max_o, label) in enumerate(odds_ranges):
    mask = (over_under_df_copy["bet_odd_num"] >= min_o) & (
        over_under_df_copy["bet_odd_num"] < max_o
    )
    if mask.sum() >= 3:
        r_won = (
            over_under_df_copy[mask]["result_winner"].astype(str).str.lower() == "yes"
        ).sum()
        r_rate = r_won / mask.sum() * 100
        if r_rate > best_wr:
            best_wr = r_rate
            best_range_idx = idx

if best_range_idx is not None:
    print(
        f"   ✅ Best range: {odds_ranges[best_range_idx][2]} ({best_wr:.1f}% win rate)"
    )
else:
    print(f"   • Not enough data for recommendation")

print(f"\n2. Strategy:")
if win_rate < 45:
    print(
        f"   ⚠️ Win rate {win_rate:.1f}% - focus on 1.80-2.00 odds (statistically safest)"
    )
elif win_rate < 50:
    print(
        f"   ⚠️ Win rate {win_rate:.1f}% - break-even zone, increase selection discipline"
    )
else:
    print(
        f"   ✅ Win rate {win_rate:.1f}% - profitable! Continue current selection method"
    )

print(f"\n3. Bankroll Management:")
print(f"   • Max stake: 3% per bet (always)")
print(f"   • Use calibrated Over 2.5 model for odds > 1.80")
print(f"   • Avoid odds < 1.50 (low margin for error)")

print(f"\n4. Risk Levels:")
print(f"   🟢 Low risk:  1.80-2.00 odds + high confidence (70%+)")
print(f"   🟡 Medium:    2.00-2.50 odds + medium confidence (55%+)")
print(f"   🔴 High risk: 3.00+ odds (requires strong edge)")

print("\n" + "=" * 80)
