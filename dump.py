from pathlib import Path
text = Path('utils/predictions.py').read_text(encoding='utf-8', errors='replace')
segment = text.split('def _normalize_odds_key',1)[1].split('def _best_fixture_odds',1)[0]
print(repr(segment[:160]))
