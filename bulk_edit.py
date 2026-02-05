from pathlib import Path
path = Path('utils/predictions.py')
text = path.read_text(encoding='utf-8')
text = text.replace('display_tips = tips[:5]', 'display_tips = tips[:8]', 1)
text = text.replace('for tip in tips[:5]:', 'for tip in tips[:8]:', 1)
text = text.replace('icon="??"', 'icon="??"')
# Insert cashout block after expander
needle = '                st.caption("Les mises sont calculees avec la bankroll, les cotes API (si disponibles) et la valeur saisie en cas d\'absence.")\n'
insert = needle + '\n    cashout_advice = _cashout_recommendations(tips, tip_meta, status, home_name, away_name)\n    if cashout_advice:\n        st.subheader("Option cashout (live)")\n        for entry in cashout_advice:\n            if entry["action"] == "cashout":\n                st.warning(f"Cashout recommande sur **{entry['label']}** : {entry['reason']}", icon="??")\n            else:\n                st.info(f"Maintien possible sur **{entry['label']}** : {entry['reason']}")\n\n'
if needle not in text:
    raise SystemExit('base needle not found')
text = text.replace(needle, insert, 1)
path.write_text(text, encoding='utf-8')
