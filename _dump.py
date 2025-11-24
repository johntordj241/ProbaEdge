from pathlib import Path
text = Path('utils/predictions.py').read_text(encoding='utf-8')
start = text.find('def _normalize_odds_key')
print('start', start)
