from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import streamlit as st

PAGE_TITLE = "ProbaEdge"
PAGE_ICON = "??"


def configure_page() -> None:
    """Declare the Streamlit page configuration exactly once."""
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")


def inject_theme() -> None:
    """Push global CSS tokens and component overrides."""
    st.markdown(
        """
        <style>
        :root {
            --color-bg: #131722;
            --color-panel: #1B202E;
            --color-text: #F0F3F5;
            --color-muted: #A0A7BB;
            --color-accent: #2ECC71;
            --color-alert: #F1A208;
            --color-danger: #E74C3C;
            --shadow-card: 0 8px 16px rgba(0,0,0,0.30);
            --shadow-card-hover: 0 12px 22px rgba(0,0,0,0.40);
            --radius-card: 12px;
            --radius-button: 8px;
            --font-primary: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: var(--color-bg);
            color: var(--color-text);
            font-family: var(--font-primary);
        }

        .stApp header { background: transparent; }
        [data-testid="stHeader"] { background: transparent; }

        [data-testid="stSidebar"] {
            background: #10131C;
            border-right: 1px solid rgba(255,255,255,0.05);
        }

        [data-testid="stSidebar"] * {
            color: var(--color-text);
        }

        [data-testid="stSidebar"] button {
            border-radius: var(--radius-button);
        }

        [data-baseweb="radio"] > div {
            background: rgba(27,32,46,0.6);
            border-radius: var(--radius-card);
            padding: 12px;
        }
        [data-baseweb="radio"] label[data-baseweb="radio"] {
            border-radius: 10px;
            margin-bottom: 4px;
            padding: 8px 12px;
            transition: background 0.2s ease, border 0.2s ease;
        }
        [data-baseweb="radio"] label[data-baseweb="radio"]:hover {
            background: rgba(46,204,113,0.15);
        }
        [data-baseweb="radio"] label[data-selected="true"] {
            border-left: 3px solid var(--color-accent);
            background: rgba(46,204,113,0.12);
        }

        .pe-page-subtitle {
            color: var(--color-muted);
            margin-bottom: 1.5rem;
            font-size: 0.95rem;
        }

        .pe-card {
            background: var(--color-panel);
            border-radius: var(--radius-card);
            box-shadow: var(--shadow-card);
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 24px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .pe-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-card-hover);
        }

        .pe-card h3, .pe-card h4 {
            color: var(--color-text);
            margin-bottom: 0.75rem;
        }

        .pe-card .pe-card-meta {
            color: var(--color-muted);
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }

        .pe-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255,255,255,0.08);
            color: var(--color-text);
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .pe-badge.accent { background: rgba(46,204,113,0.14); color: #BFF6D8; }
        .pe-badge.alert { background: rgba(241,162,8,0.16); color: #F7C46A; }
        .pe-badge.danger { background: rgba(231,76,60,0.18); color: #F7B1A6; }

        .pe-chip {
            display: inline-flex;
            align-items: center;
            background: rgba(255,255,255,0.08);
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 0.78rem;
            margin: 0 6px 6px 0;
            color: var(--color-text);
        }

        .pe-section-title {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--color-muted);
            margin-bottom: 8px;
        }

        .stMetric {
            background: var(--color-panel);
            border-radius: var(--radius-card);
            border: 1px solid rgba(255,255,255,0.05);
            padding: 16px;
            box-shadow: var(--shadow-card);
        }
        .stMetric label {
            color: var(--color-muted) !important;
        }
        .stMetric div[data-testid="stMetricValue"] {
            color: var(--color-text) !important;
        }

        .stButton > button {
            background: var(--color-accent);
            color: #0B170F;
            font-weight: 600;
            border-radius: var(--radius-button);
            border: none;
            padding: 0.55rem 1.4rem;
            transition: transform 0.15s ease, box-shadow 0.2s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(46,204,113,0.3);
        }
        .stButton.secondary > button {
            background: transparent;
            border: 1px solid var(--color-accent);
            color: var(--color-accent);
        }
        .stButton.secondary > button:hover {
            background: rgba(46,204,113,0.1);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(27,32,46,0.7);
            border-radius: var(--radius-button);
            padding: 10px 16px;
            color: var(--color-muted);
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: rgba(46,204,113,0.18);
            color: var(--color-text);
        }

        .stCheckbox > label,
        .stRadio > label,
        label {
            color: var(--color-muted) !important;
        }

        input, textarea, select, .stSelectbox div[data-baseweb="select"] > div {
            background: rgba(19,23,34,0.85);
            color: var(--color-text);
            border-radius: var(--radius-button);
            border: 1px solid rgba(255,255,255,0.08);
        }

        .stDataFrame, .stTable {
            background: transparent;
        }
        .stDataFrame [data-testid="stTable"] > div > div:nth-child(2) {
            background: transparent;
        }
        .stDataFrame thead tr {
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-muted);
            background: rgba(255,255,255,0.05);
        }
        .stDataFrame tbody tr:nth-child(even) {
            background: rgba(255,255,255,0.02);
        }
        .stDataFrame tbody tr:hover {
            background: rgba(46,204,113,0.08);
        }

        .stSlider > div > div > div {
            background: rgba(46,204,113,0.25);
        }
        .stSlider > div > div > div > div[data-baseweb="slider"] > div {
            background: var(--color-accent);
        }
        .stSlider > div > div > div > div[data-baseweb="slider"] > div > div {
            box-shadow: 0 0 0 4px rgba(46,204,113,0.15);
        }

        .pe-floating-button button {
            position: sticky;
            bottom: 24px;
            width: 100%;
            z-index: 5;
        }

        .pe-spinner {
            width: 38px;
            height: 38px;
            border: 3px solid rgba(46,204,113,0.3);
            border-top-color: #2ECC71;
            border-radius: 999px;
            animation: spin 0.8s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def card(title: Optional[str] = None, subtitle: Optional[str] = None) -> Iterator[st.delta_generator.DeltaGenerator]:
    """Utility context manager to render content inside a styled card."""
    outer = st.container()
    outer.markdown('<div class="pe-card">', unsafe_allow_html=True)
    inner = outer.container()
    if title:
        inner.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
    if subtitle:
        inner.markdown(f"<div class=\"pe-card-meta\">{subtitle}</div>", unsafe_allow_html=True)
    try:
        yield inner
    finally:
        outer.markdown('</div>', unsafe_allow_html=True)


def badge(text: str, tone: str = "accent") -> str:
    tone_class = tone if tone in {"accent", "alert", "danger"} else ""
    return f"<span class=\"pe-badge {tone_class}\">{text}</span>"


def chip(text: str) -> str:
    return f"<span class=\"pe-chip\">{text}</span>"


__all__ = [
    "configure_page",
    "inject_theme",
    "card",
    "badge",
    "chip",
]
