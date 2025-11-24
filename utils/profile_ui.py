from __future__ import annotations

from typing import List, Dict, Optional

import json
import streamlit as st

from .profile import (
    DEFAULT_BANKROLL,
    DEFAULT_INTENSITY_WEIGHTS,
    DEFAULT_UI_DEFAULTS,
    aliases_map,
    add_favorite_competition,
    delete_bookmaker,
    get_bankroll_settings,
    get_custom_bookmakers,
    get_favorite_competitions,
    get_intensity_weights,
    get_ui_defaults,
    remove_favorite_competition,
    load_profile,
    save_bankroll_settings,
    save_intensity_weights,
    save_profile,
    save_ui_defaults,
    upsert_bookmaker,
)
from .ui_helpers import load_leagues
from .match_filter import BOOKMAKER_PRESETS


def _render_custom_list(custom: List[dict[str, any]]) -> None:
    if not custom:
        st.info("Aucun bookmaker personnalise pour le moment.")
        return
    for item in custom:
        cols = st.columns([3, 2, 1])
        cols[0].markdown(f"**{item['label']}**")
        aliases_text = ", ".join(item.get("aliases", [])) or "(aucun alias)"
        cols[1].caption(aliases_text)
        if cols[2].button("Supprimer", key=f"delete_{item['label']}"):
            delete_bookmaker(item['label'])
            st.experimental_rerun()


def _strategy_display_map() -> Dict[str, str]:
    return {
        "flat": "Mise fixe",
        "percent": "Pourcentage fixe",
        "kelly": "Kelly simplifie",
    }


def show_profile() -> None:
    st.header("Profil utilisateur")
    st.caption("Personnaliser les parametres, la bankroll et definir vos bookmakers favoris.")

    profile = load_profile()
    bankroll = get_bankroll_settings()

    st.subheader("Gestion de bankroll")
    help_text = "Configurez le capital disponible et la strategie de mise appliquee aux recommandations."
    with st.expander("Parametres de bankroll", expanded=True):
        strategy_labels = _strategy_display_map()
        strategy_codes = list(strategy_labels.keys())
        strategy_values = [strategy_labels[code] for code in strategy_codes]
        current_code = bankroll.get("strategy", "percent")
        try:
            current_index = strategy_codes.index(current_code)
        except ValueError:
            current_index = 0
        with st.form("bankroll_form"):
            amount = st.number_input(
                "Capital disponible (EUR)",
                min_value=0.0,
                value=float(bankroll.get("amount", DEFAULT_BANKROLL["amount"])),
                step=10.0,
                help=help_text,
            )
            selected_label = st.selectbox(
                "Strategie de mise",
                strategy_values,
                index=current_index,
            )
            strategy = strategy_codes[strategy_values.index(selected_label)]

            flat_stake = st.number_input(
                "Mise fixe (EUR)",
                min_value=0.0,
                value=float(bankroll.get("flat_stake", DEFAULT_BANKROLL["flat_stake"])),
                step=1.0,
                help="Utilise uniquement la strategie 'Mise fixe'.",
            )
            percent = st.number_input(
                "Pourcentage fixe du capital (%)",
                min_value=0.0,
                value=float(bankroll.get("percent", DEFAULT_BANKROLL["percent"])),
                step=0.5,
                help="Utilise uniquement la strategie 'Pourcentage fixe'.",
            )
            kelly_fraction = st.slider(
                "Fraction Kelly (0-1)",
                min_value=0.0,
                max_value=1.0,
                value=float(bankroll.get("kelly_fraction", DEFAULT_BANKROLL["kelly_fraction"])),
                step=0.05,
                help="Multiplier du taux Kelly theorique (1 = Kelly complet).",
            )
            default_odds = st.number_input(
                "Cote de reference",
                min_value=1.01,
                value=float(bankroll.get("default_odds", DEFAULT_BANKROLL["default_odds"])),
                step=0.05,
                help="Cote par defaut utilisee pour calculer les mises lorsque aucune cote n'est fournie.",
            )
            col_min, col_max = st.columns(2)
            min_stake = col_min.number_input(
                "Mise minimale (EUR)",
                min_value=0.0,
                value=float(bankroll.get("min_stake", DEFAULT_BANKROLL["min_stake"])),
                step=1.0,
            )
            max_stake = col_max.number_input(
                "Mise maximale (EUR)",
                min_value=0.0,
                value=float(bankroll.get("max_stake", DEFAULT_BANKROLL["max_stake"])),
                step=5.0,
            )

            submitted_bankroll = st.form_submit_button("Enregistrer la bankroll")
            if submitted_bankroll:
                save_bankroll_settings(
                    {
                        "amount": amount,
                        "strategy": strategy,
                        "flat_stake": flat_stake,
                        "percent": percent,
                        "kelly_fraction": kelly_fraction,
                        "default_odds": default_odds,
                        "min_stake": min_stake,
                        "max_stake": max_stake,
                    }
                )
                st.success("Parametres de bankroll enregistres.")
                st.experimental_rerun()
    st.subheader("Ponderation intensite match")
    with st.expander("Ajuster les composantes", expanded=False):
        current_weights = get_intensity_weights()
        with st.form("intensity_weights_form"):
            xg_weight = st.slider(
                "Poids xG attendus",
                min_value=0.0,
                max_value=1.0,
                value=float(current_weights.get("xg", DEFAULT_INTENSITY_WEIGHTS["xg"])),
                step=0.05,
            )
            over_weight = st.slider(
                "Poids Over 2.5",
                min_value=0.0,
                max_value=1.0,
                value=float(current_weights.get("over", DEFAULT_INTENSITY_WEIGHTS["over"])),
                step=0.05,
            )
            btts_weight = st.slider(
                "Poids BTTS",
                min_value=0.0,
                max_value=1.0,
                value=float(current_weights.get("btts", DEFAULT_INTENSITY_WEIGHTS["btts"])),
                step=0.05,
            )
            submitted_weights = st.form_submit_button("Enregistrer les ponderations")
            if submitted_weights:
                save_intensity_weights(
                    {
                        "xg": xg_weight,
                        "over": over_weight,
                        "btts": btts_weight,
                    }
                )
                st.success("Ponderations enregistrees.")
                st.experimental_rerun()

    st.subheader("Bookmakers personnalises")
    with st.expander("Ajouter ou modifier", expanded=False):
        with st.form("bookmaker_form"):
            label = st.text_input("Nom du bookmaker", placeholder="ex: Winamax")
            aliases_raw = st.text_input(
                "Alias visibles dans l'API (separes par des virgules)",
                help="Ex: winamax, winamaxfr",
            )
            submitted = st.form_submit_button("Enregistrer")
            if submitted:
                aliases = [alias.strip() for alias in aliases_raw.split(",") if alias.strip()]
                upsert_bookmaker(label, aliases)
                st.success("Bookmaker enregistre.")
                st.experimental_rerun()

    _render_custom_list(get_custom_bookmakers())

    st.markdown("---")
    st.subheader("Competitions favorites")
    favorites = get_favorite_competitions()
    with st.expander("Ajouter ou supprimer des favoris", expanded=False):
        if favorites:
            for fav in favorites:
                fav_cols = st.columns([3, 2, 1])
                label = fav.get("label") or f"Ligue {fav.get('league_id')}"
                fav_cols[0].markdown(f"**{label}**")
                season_text = fav.get("season") if fav.get("season") else "Auto"
                fav_cols[1].caption(f"Ligue #{fav.get('league_id')} | Saison {season_text}")
                if fav_cols[2].button("Supprimer", key=f"remove_fav_{fav.get('league_id')}_{fav.get('season')}"):
                    remove_favorite_competition(fav.get("league_id"), fav.get("season"))
                    st.experimental_rerun()
        else:
            st.info("Aucun favori enregistre pour le moment.")

        leagues = load_leagues()
        if leagues:
            with st.form("favorite_competition_form"):
                league_option = st.selectbox(
                    "Choisir une competition",
                    options=leagues,
                    format_func=lambda item: item.get("label", "Competition"),
                )
                season_list = league_option.get("seasons") or []
                if not season_list and league_option.get("current_season"):
                    season_list = [league_option["current_season"]]
                season_value: Optional[int] = None
                if season_list:
                    season_value = st.selectbox("Saison", season_list, index=0)
                label_value = st.text_input(
                    "Nom du favori",
                    value=league_option.get("label", "Favori"),
                    help="Intitule qui apparaitra dans la selection rapide.",
                )
                submitted_favorite = st.form_submit_button("Ajouter aux favoris")
                if submitted_favorite:
                    add_favorite_competition(
                        league_option.get("id"),
                        int(season_value) if season_value is not None else None,
                        label_value or league_option.get("label", "Favori"),
                        country=league_option.get("country"),
                        comp_type=league_option.get("type"),
                        categories=league_option.get("categories"),
                        query="",
                    )
                    st.success("Favori enregistre.")
                    st.experimental_rerun()
        else:
            st.warning("Impossible de charger les competitions pour ajouter un favori (verifier la connexion).")

    st.markdown("---")
    st.subheader("Vues par defaut")
    ui_defaults = get_ui_defaults()
    with st.form("ui_defaults_form"):
        favorites = get_favorite_competitions()
        selected_favorite = None
        if favorites:
            favorite_labels = ["Aucun"] + [
                fav.get("label", f"Ligue {fav.get('league_id')}") for fav in favorites
            ]
            default_fav_label = "Aucun"
            for idx, fav in enumerate(favorites, start=1):
                if fav.get("league_id") == ui_defaults.get("league_id") and (
                    fav.get("season") in {None, ui_defaults.get("season")}
                ):
                    default_fav_label = favorite_labels[idx]
                    break
            selected_label = st.selectbox(
                "Prefill depuis un favori",
                favorite_labels,
                index=favorite_labels.index(default_fav_label),
            )
            if selected_label != "Aucun":
                selected_favorite = favorites[favorite_labels.index(selected_label) - 1]

        leagues = load_leagues()
        league_id_pref = ui_defaults.get("league_id")
        season_pref = ui_defaults.get("season")
        if selected_favorite:
            league_id_pref = selected_favorite.get("league_id", league_id_pref)
            season_pref = selected_favorite.get("season", season_pref)

        if leagues:
            league_index = 0
            for idx, league in enumerate(leagues):
                try:
                    if int(league.get("id")) == int(league_id_pref):
                        league_index = idx
                        break
                except (TypeError, ValueError):
                    continue
            selected_league = st.selectbox(
                "Ligue par defaut",
                options=leagues,
                index=min(league_index, len(leagues) - 1),
                format_func=lambda item: item.get("label", "Ligue"),
            )
            season_options = selected_league.get("seasons") or []
            if not season_options and selected_league.get("current_season"):
                season_options = [selected_league["current_season"]]
            if not season_options:
                season_pref = None
                season_options = [ui_defaults.get("season") or selected_league.get("current_season") or 2025]

            if season_pref in season_options:
                season_index = season_options.index(season_pref)
            else:
                season_index = 0
            season_value = st.selectbox(
                "Saison par defaut",
                season_options,
                index=min(season_index, len(season_options) - 1),
            )
        else:
            st.warning("Impossible de charger les ligues. Les vues par defaut ne pourront pas etre sauvegardees.")
            selected_league = None
            season_value = None

        custom_alias_map = aliases_map()
        bookmaker_options = list(BOOKMAKER_PRESETS.keys()) + sorted(custom_alias_map.keys())
        default_bookmakers = [
            entry for entry in ui_defaults.get("bookmakers", []) if entry in bookmaker_options
        ]
        if not default_bookmakers:
            default_bookmakers = bookmaker_options
        bookmaker_selection = st.multiselect(
            "Bookmakers par defaut",
            bookmaker_options,
            default=default_bookmakers,
            help="Selection appliquee automatiquement dans les pages Bookmakers et Analytics.",
        )
        horizon_default = int(ui_defaults.get("horizon_days", DEFAULT_UI_DEFAULTS["horizon_days"]))
        horizon_value = st.slider(
            "Horizon Bookmakers (jours)",
            min_value=1,
            max_value=7,
            value=min(max(horizon_default, 1), 7),
            help="Nombre de journees chargees par defaut dans la page Bookmakers.",
        )

        if st.form_submit_button("Enregistrer les vues par defaut"):
            if selected_league is None:
                st.error("Selectionnez une ligue avant de sauvegarder.")
            else:
                payload = {
                    "league_id": int(selected_league.get("id")),
                    "season": int(season_value) if season_value is not None else None,
                    "bookmakers": bookmaker_selection,
                    "horizon_days": int(horizon_value),
                }
                save_ui_defaults(payload)
                st.success("Vues par defaut enregistrees.")
                st.experimental_rerun()

    st.markdown("---")
    st.subheader("Export du profil")
    st.caption("Sauvegarde et edition manuelle des preferences.")
    profile_json = st.text_area(
        "Donnees JSON",
        value=json.dumps(load_profile(), ensure_ascii=False, indent=2),
        height=180,
    )
    if st.button("Sauvegarder les donnees JSON"):
        try:
            parsed = json.loads(profile_json)
            save_profile(parsed)
            st.success("Profil mis a jour.")
        except json.JSONDecodeError as exc:
            st.error(f"Format JSON invalide: {exc}")

    st.markdown("---")
    custom_alias_map = aliases_map()
    if custom_alias_map:
        st.caption(
            "Alias actuellement pris en compte: "
            + ", ".join(
                f"{label} -> {', '.join(aliases) or 'aucun alias'}" for label, aliases in custom_alias_map.items()
            )
        )

__all__ = ["show_profile"]


