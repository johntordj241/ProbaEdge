from pathlib import Path
text = Path('utils/predictions.py').read_text(encoding='utf-8')
import sys
sys.exit(text.count("ODDS_MARKET_MAIN"))
