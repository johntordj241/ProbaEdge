from __future__ import annotations



from typing import Any, Dict, Optional



import streamlit as st

from streamlit.components.v1 import html as st_html



from .config import get_api_key



WIDGET_SCRIPT_URL = "https://widgets.api-sports.io/3.1.0/widgets.js"

_DEFAULT_CONFIG: Dict[str, Any] = {

    "sport": "football",

    "lang": "fr",

    "theme": "dark",

    "show-logos": True,

    "favorites": True,

    "refresh": 60,

    "target-game": "modal",

    "target-team": "modal",

    "target-player": "modal",
    "target-league": "modal",

}





def _normalize_attr_value(value: Any) -> Optional[str]:

    if value is None:

        return None

    if isinstance(value, bool):

        return "true" if value else "false"

    return str(value)





def _format_attrs(attrs: Dict[str, Any]) -> str:

    parts: list[str] = []

    for raw_key, raw_value in attrs.items():

        normalized = _normalize_attr_value(raw_value)

        if normalized in {None, ""}:

            continue

        attr_name = raw_key if raw_key.startswith("data-") else f"data-{raw_key}".replace("_", "-")

        parts.append(f'{attr_name}="{normalized}"')

    return " ".join(parts)





def _widget_tag(widget_type: str, attrs: Dict[str, Any]) -> str:

    merged = dict(attrs)

    merged.setdefault("type", widget_type)

    return f"<api-sports-widget {_format_attrs(merged)}></api-sports-widget>"





def build_widget_html(

    widget_type: str,

    *,

    config: Optional[Dict[str, Any]] = None,

    **widget_attrs: Any,

) -> Optional[str]:
    try:
        api_key = get_api_key()
    except RuntimeError:
        return None



    widget_tag = _widget_tag(widget_type, widget_attrs)



    config_attrs: Dict[str, Any] = dict(_DEFAULT_CONFIG)

    if config:

        config_attrs.update(config)

    config_attrs.setdefault("key", api_key)



    config_tag = _widget_tag("config", config_attrs)

    script_tag = f'<script type="module" src="{WIDGET_SCRIPT_URL}"></script>'

    return "\n".join([widget_tag, config_tag, script_tag])





def render_widget(

    widget_type: str,

    *,

    height: int = 640,

    scrolling: bool = False,

    config: Optional[Dict[str, Any]] = None,

    **widget_attrs: Any,

) -> None:

    markup = build_widget_html(widget_type, config=config, **widget_attrs)

    if not markup:

        st.info("Cle API requise pour les widgets officiels API-SPORTS.")

        return

    st_html(markup, height=height, scrolling=scrolling)





__all__ = ["build_widget_html", "render_widget", "WIDGET_SCRIPT_URL"]

