"""
Aegis — Plateforme de prévention du crime financier.

Point d'entrée unique du jury :  streamlit run app.py

Cette interface est la coquille de navigation multi-persona. Toute la logique
« entreprise » vit dans le package ``aegis/`` ; le moteur noté
(``fraud_detection.detect_fraud``) reste inchangé et alimente le coeur
deterministe de l'orchestrateur de décision.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from aegis import __version__
from aegis.config import CONFIG, DB_PATH
from aegis.casemgmt import CaseStore
from aegis.data import load_from_csv
from aegis.engine import DecisionEngine
from aegis.ui import theme
from aegis.ui.pages import (
    analyst,
    communications,
    compliance,
    demo,
    executive,
    investigator,
    monitoring,
)

ROOT = Path(__file__).resolve().parent
DEMO_CSV = ROOT / "data" / "demo_transactions.csv"
SAMPLE_CSV = ROOT / "data" / "sample_transactions.csv"

PERSONAS = {
    "Console Analyste": analyst,
    "Atelier d'investigation": investigator,
    "Supervision temps réel": monitoring,
    "Communications & réponse": communications,
    "Tableau de bord Direction": executive,
    "Conformité & Audit": compliance,
    "Démo guidée": demo,
}


@st.cache_resource
def get_store() -> CaseStore:
    return CaseStore(DB_PATH)


@st.cache_resource
def get_engine() -> DecisionEngine:
    return DecisionEngine(CONFIG)


@st.cache_data(show_spinner=False)
def load_transactions_cached(source: str, payload: bytes | None) -> list[dict]:
    """Charge les transactions selon la source choisie (mise en cache)."""
    if source == "upload" and payload is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        return load_from_csv(tmp_path)
    if source == "sample":
        return load_from_csv(str(SAMPLE_CSV))
    return load_from_csv(str(DEMO_CSV))


def build_dataframe(decisions: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Transaction": d["transaction_id"],
        "Client": d["user_masked"],
        "Montant": d["amount"],
        "Devise": d["currency"],
        "Pays": d["country"],
        "Score": d["fraud_score"],
        "Niveau": d["level"],
        "Motif": d["reason"],
        "Suspecte": d["is_suspicious"],
    } for d in decisions])


def sidebar() -> tuple[str, str, bytes | None, str]:
    with st.sidebar:
        theme.brand_header()
        st.divider()
        theme_mode = theme.theme_selector()
        st.divider()

        st.caption("SOURCE DE DONNÉES")
        source_label = st.radio(
            "Source", ["Jeu de démonstration", "Échantillon hackathon", "Importer un CSV"],
            label_visibility="collapsed",
        )
        payload = None
        source = "demo"
        if source_label == "Échantillon hackathon":
            source = "sample"
        elif source_label == "Importer un CSV":
            source = "upload"
            up = st.file_uploader("Fichier CSV", type=["csv"],
                                  label_visibility="collapsed")
            payload = up.getvalue() if up else None
            if payload is None:
                st.info("En attente d'un fichier — démo affichée.")
                source = "demo"

        st.divider()
        st.caption("VOTRE IDENTITÉ (audit)")
        st.session_state["current_user"] = st.text_input(
            "Analyste", value=st.session_state.get("current_user", "A. Diallo"),
            label_visibility="collapsed")

        st.divider()
        st.caption("ESPACE DE TRAVAIL")
        persona = st.radio("Persona", list(PERSONAS.keys()),
                           label_visibility="collapsed")

        st.divider()
        if st.button("Réinitialiser les dossiers", use_container_width=True):
            get_store().reset()
            st.toast("Dossiers et piste d'audit réinitialisés.")

    return persona, source, payload, theme_mode


def main() -> None:
    st.set_page_config(page_title="Aegis — Financial Crime Intelligence",
                       page_icon="🛡️", layout="wide")

    persona, source, payload, theme_mode = sidebar()
    theme.inject(theme_mode)

    transactions = load_transactions_cached(source, payload)
    engine = get_engine()
    decisions = engine.analyze(transactions)
    df = build_dataframe(decisions)
    store = get_store()

    ctx = {
        "transactions": transactions,
        "decisions": decisions,
        "engine": engine,
        "store": store,
        "df": df,
        "config": CONFIG,
        "theme_mode": theme_mode,
    }

    PERSONAS[persona].render(ctx)

    st.divider()
    st.caption(
        f"Aegis v{__version__} · moteur ML : {engine.ml_backend.replace('_', ' ')} · "
        f"coeur deterministe noté préservé (detect_fraud) · "
        f"{len(transactions)} transactions · PII pseudonymisées (RGPD)"
    )


if __name__ == "__main__":
    main()
