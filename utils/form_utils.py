from __future__ import annotations

from typing import Optional, Sequence

FORM_LABELS = {
    "W": "V",
    "L": "D",
    "D": "N",
    "V": "V",
    "N": "N",
}

FORM_CLASSES = {
    "W": "win",
    "V": "win",
    "L": "loss",
    "D": "loss",
    "N": "draw",
}

FORM_STYLE = """
<style>
.form-table {
    border-collapse: collapse;
    width: 100%;
}
.form-table td {
    padding: 4px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
.form-table td.team {
    font-weight: 600;
    width: 30%;
}
.form-badge {
    display: inline-block;
    width: 22px;
    height: 22px;
    line-height: 22px;
    text-align: center;
    border-radius: 4px;
    margin-right: 4px;
    color: #fff;
    font-size: 0.8rem;
}
.form-badge.win { background-color: #2ecc71; }
.form-badge.draw { background-color: #f1c40f; color: #111; }
.form-badge.loss { background-color: #e74c3c; }
.form-badge.neutral { background-color: #7f8c8d; }
</style>
"""


def form_badges_html(form: Optional[str]) -> str:
    if not form:
        return "<span class='form-badge neutral'>-</span>"
    badges: list[str] = []
    cleaned = form.replace(" ", "").replace(",", "")
    for char in cleaned.strip():
        label = FORM_LABELS.get(char.upper(), char.upper())
        css_class = FORM_CLASSES.get(char.upper(), "neutral")
        badges.append(f"<span class='form-badge {css_class}'>{label}</span>")
    return "".join(badges)


def render_form_table(teams: Sequence[dict[str, str]]) -> str:
    rows_html = []
    for entry in teams:
        rows_html.append(
            f"<tr><td class='team'>{entry.get('team', '?')}</td>"
            f"<td>{form_badges_html(entry.get('form'))}</td></tr>"
        )
    return FORM_STYLE + f"""
    <table class="form-table">
        {''.join(rows_html)}
    </table>
    """


__all__ = ["render_form_table", "form_badges_html", "FORM_STYLE"]
