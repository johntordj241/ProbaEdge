from pathlib import Path
import re
path = Path('utils/dashboard.py')
text = path.read_text(encoding='utf-8')
new_game = '''def _widget_game_html(fixture_id: Optional[int], theme: str = "dark") -> Optional[str]:
    if not fixture_id:
        return None
    return build_widget_html(
        "game",
        config={"theme": theme},
        game_id=fixture_id,
    )

'''
text, count_game = re.subn(
    r'def _widget_game_html\(.*?\) -> Optional\[str\]:\r?\n(?:    .+\r?\n)+?"""\.strip\(\)\r?\n\r?\n',
    new_game,
    text,
    count=1,
    flags=re.S,
)
if count_game != 1:
    raise SystemExit(f'Unable to update _widget_game_html (replaced {count_game} times)')
new_standings = '''def _widget_standings_html(league_id: int, season: int, theme: str = "dark") -> Optional[str]:
    if not league_id or not season:
        return None
    return build_widget_html(
        "standings",
        config={"theme": theme},
        league=league_id,
        season=season,
    )

'''
text, count_std = re.subn(
    r'def _widget_standings_html\(.*?\) -> Optional\[str\]:\r?\n(?:    .+\r?\n)+?"""\.strip\(\)\r?\n\r?\n',
    new_standings,
    text,
    count=1,
    flags=re.S,
)
if count_std != 1:
    raise SystemExit(f'Unable to update _widget_standings_html (replaced {count_std} times)')
if 'from .widgets import build_widget_html\n' not in text:
    text = text.replace('from .config import API_KEY\r\n', '')
    text = text.replace('from .config import API_KEY\n', '')
    insertion_point = text.index('from .prediction_model')
    text = text[:insertion_point] + 'from .widgets import build_widget_html\n' + text[insertion_point:]
else:
    text = text.replace('from .config import API_KEY\n', '')
text = text.replace('WIDGET_SCRIPT_URL = "https://widgets.api-sports.io/2.0.3/widgets.js"\r\n\r\n', '')
text = text.replace('WIDGET_SCRIPT_URL = "https://widgets.api-sports.io/2.0.3/widgets.js"\n\n', '')
path.write_text(text, encoding='utf-8')
