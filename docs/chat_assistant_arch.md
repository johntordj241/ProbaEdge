# Assistant conversationnel ProbaEdge

## Vision générale

| Couche             | Description                                                                                          |
|--------------------|------------------------------------------------------------------------------------------------------|
| Interface          | Page Streamlit dédiée (`show_chat_assistant`) basée sur `st.chat_message` / `st.chat_input`.         |
| Orchestrateur      | `utils/chat_assistant.py` : charge l’historique, calcule stats (edge, ROI, Kelly), construit le prompt. |
| Mémoire            | Supabase + `pgvector` (table `chat_memory`) pour conserver le contexte long terme. Fallback session. |
| IA                 | OpenAI GPT‑4‑turbo pour le raisonnement, `text-embedding-3-large` pour l’indexation mémoire.         |
| Données            | `prediction_history.csv`, modules existants (`bankroll`, `prediction_model`, etc.).                  |

## Flux principal

1. L’utilisateur saisit une question → `handle_chat_query`.
2. Chargement de `prediction_history.csv` (via `load_prediction_history`) + calcul :
   - matches à forte probabilité / edge,
   - ROI global et récent,
   - propositions de mise (Kelly/percent) en respectant la bankroll.
3. Récupération du contexte Supabase (mémoire conversationnelle).
4. Construction du prompt système (ton neutre, discipline) + messages utilisateur.
5. Appel GPT‑4‑turbo (OpenAI Responses API). Les erreurs 401/clé invalide sont traduites en message utilisateur.
6. Stockage Q/R dans Supabase + session_state et restitution dans l’UI.

## Modules créés

- `utils/chat_prompts.py` : prompt système + helpers.
- `utils/chat_assistant.py` :
  - `handle_chat_query(message, context)` (point d’entrée),
  - calculs edge/ROI/Kelly,
  - gestion mémoire (Supabase + fallback),
  - appel OpenAI (chat + embeddings).
- `utils/chat_ui.py` : rendering Streamlit (page Assistant).
- `tests/test_chat_assistant.py` : tests unitaires (stats + mock LLM).

## Principes métier intégrés

- Jamais pousser à parier / pas d’urgence.
- Valoriser l’abstention si edge < seuil.
- Rappeler systématiquement bankroll, filtres, discipline.
- Ton neutre et factuel.
- En cas de question d’introduction (« Qui es-tu ? », « Comment tu fonctionnes ? »),
  l’assistant se présente en une phrase avant de recadrer la conversation sur l’analyse.

## Intégrations

- Bankroll : `utils.bankroll.suggest_stake`.
- Historique : `utils.prediction_history.load_prediction_history`.
- Supabase : `utils.supabase_client.get_supabase_client`.
- Cache session : `st.session_state["assistant_messages"]`.
- Coach widget : `utils.coach_ui.render_coach_widget` reutilise `handle_chat_query` pour la bulle en bas a droite.

## Points à configurer

- Table Supabase `chat_memory` (colonnes : `user_id`, `question`, `answer`, `embedding`, `created_at`).
- Variables d’environnement : `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.

Le module reste fonctionnel hors connexion Supabase (les conversations restent alors limitées à la session en cours).***
