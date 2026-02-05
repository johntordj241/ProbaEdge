from pathlib import Path

path = Path("utils/fixtures.py")
text = path.read_text(encoding="utf-8")
if "streamlit_autorefresh" not in text:
    text = text.replace(
        "import streamlit as st\n\nfrom .api_calls",
        "import streamlit as st\n\ntry:\n    from streamlit_autorefresh import st_autorefresh\nexcept ImportError:\n    st_autorefresh = None\n\nfrom .api_calls",
        1,
    )
old_block = "    else:\n        status_filter = LIVE_STATUS_CODES\n        live_param = \"all\"\n\n    with st.spinner(\"Chargement des matchs...\"):\n"
if old_block not in text:
    raise SystemExit('live block not found')
new_block = "    else:\n        status_filter = LIVE_STATUS_CODES\n        live_param = \"all\"\n        if st_autorefresh:\n            st_autorefresh(interval=45_000, key=f\"fixtures_live_{league_id}\")\n        else:\n            st.caption(\"Actualise la page pour suivre le direct.\")\n\n    with st.spinner(\"Chargement des matchs...\"):\n"
text = text.replace(old_block, new_block, 1)
path.write_text(text, encoding="utf-8")
