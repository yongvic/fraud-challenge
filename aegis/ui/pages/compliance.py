"""
Conformité & Audit — la vue du responsable conformité et du régulateur.

Piste d'audit immuable (qui/quoi/quand/pourquoi), explicabilité des décisions
(reason codes), et export réglementaire. Répond aux exigences de traçabilité
(LCB-FT / AML), du droit à l'explication (RGPD) et de la gouvernance modèle.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from aegis.ui.components import empty_state, kpi_strip, page_header


def render(ctx) -> None:
    store = ctx["store"]
    decisions = ctx["decisions"]
    engine = ctx["engine"]

    page_header(
        "Gouvernance",
        "Conformité & Audit",
        "Traçabilité complète des décisions et explicabilité réglementaire. "
        "Chaque alerte et chaque action humaine sont journalisées de façon immuable.",
    )

    store.sync_alerts(decisions, actor="system")
    trail = store.audit_trail()
    m = store.feedback_metrics()

    kpi_strip([
        ("Événements audités", str(len(trail)), "piste immuable"),
        ("Modèle ML", engine.ml_backend.replace("_", " "), "moteur d'anomalie"),
        ("Dossiers résolus", str(m["resolved"]), "avec disposition"),
        ("Taux faux positifs", f"{m['false_positive_rate']*100:.0f}%"
         if m["false_positive_rate"] is not None else "—", "qualité décisionnelle"),
    ])
    st.write("")

    tab_audit, tab_explain, tab_export = st.tabs(
        ["Piste d'audit", "Explicabilité des décisions", "Export réglementaire"])

    with tab_audit:
        if not trail:
            empty_state("Aucun événement", "Les actions apparaîtront ici.")
        else:
            st.dataframe(pd.DataFrame(trail)[["ts", "actor", "action",
                         "transaction_id", "detail"]],
                         use_container_width=True, hide_index=True)

    with tab_explain:
        st.caption("Décomposition des reason codes par décision (droit à l'explication).")
        rows = []
        for d in decisions:
            rows.append({
                "Transaction": d["transaction_id"],
                "Client (pseudonymisé)": d["user_masked"],
                "Score": d["fraud_score"],
                "Niveau": d["level"],
                "Couche règles": d["rule_score"],
                "Couche ML": d["ml_score"],
                "Couche réseau": d["ring_score"],
                "Reason codes": ", ".join(d["reason_codes"]) or "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_export:
        st.caption("Export pseudonymisé (PII masquées) pour le régulateur ou le SI conformité.")
        export_rows = []
        for d in decisions:
            if d["is_suspicious"]:
                export_rows.append({
                    "transaction_id": d["transaction_id"],
                    "client_pseudonyme": d["user_masked"],
                    "score": d["fraud_score"],
                    "niveau": d["level"],
                    "motif": d["reason"],
                    "reason_codes": "|".join(d["reason_codes"]),
                    "pays": d["country"],
                    "horodatage": d["timestamp"],
                })
        if export_rows:
            buf = StringIO()
            pd.DataFrame(export_rows).to_csv(buf, index=False)
            st.download_button("Télécharger le rapport réglementaire (CSV)",
                               data=buf.getvalue(),
                               file_name="aegis_rapport_conformite.csv",
                               mime="text/csv")
            st.dataframe(pd.DataFrame(export_rows), use_container_width=True,
                         hide_index=True)
        else:
            empty_state("Aucune alerte à exporter", "Aucune transaction signalée.")
