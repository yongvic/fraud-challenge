"""
Supervision temps réel — le mur d'écran d'un centre opérationnel.

Rejoue le flux de transactions de façon chronologique (simulation d'un flux
temps réel) et fait apparaître les alertes au fil de l'eau. Inclut un panneau de
qualité des données (observabilité du pipeline avant décision).
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from fraud_detection import _parse_timestamp
from aegis.data.ingest import data_quality_report
from aegis.ui.components import alert_card, kpi_strip, page_header


def render(ctx) -> None:
    transactions = ctx["transactions"]
    decisions = ctx["decisions"]

    page_header(
        "Supervision",
        "Flux temps réel",
        "Rejoue la journée transaction par transaction. Les alertes émergent au "
        "fil de l'eau, comme dans un centre opérationnel.",
    )

    tab_stream, tab_quality = st.tabs(["Flux en direct", "Qualité des données"])

    with tab_stream:
        # Ordonne les décisions chronologiquement.
        order = sorted(
            range(len(decisions)),
            key=lambda i: (_parse_timestamp(decisions[i].get("timestamp")) is None,
                           _parse_timestamp(decisions[i].get("timestamp"))
                           or _parse_timestamp("1970-01-01T00:00:00Z")),
        )
        ordered = [decisions[i] for i in order]

        c1, c2 = st.columns([1, 1])
        speed = c1.select_slider("Vitesse", ["Lent", "Normal", "Rapide"], value="Normal")
        run = c2.button("Rejouer le flux", type="primary", use_container_width=True)
        delay = {"Lent": 0.5, "Normal": 0.25, "Rapide": 0.08}[speed]

        kpi_slot = st.empty()
        feed_slot = st.empty()

        if run:
            seen_alerts = []
            for k, d in enumerate(ordered, start=1):
                if d["is_suspicious"]:
                    seen_alerts.append(d)
                with kpi_slot.container():
                    kpi_strip([
                        ("Traitées", str(k), f"/ {len(ordered)}"),
                        ("Alertes", str(len(seen_alerts)), "détectées"),
                        ("Dernier score", f"{d['fraud_score']:.2f}", d["level"]),
                    ])
                with feed_slot.container():
                    for d2 in reversed(seen_alerts[-6:]):
                        alert_card(d2)
                time.sleep(delay)
            if not seen_alerts:
                st.success("Flux terminé : aucune alerte.")
        else:
            alerts = [d for d in ordered if d["is_suspicious"]]
            with kpi_slot.container():
                kpi_strip([
                    ("Transactions", str(len(ordered)), "dans le flux"),
                    ("Alertes", str(len(alerts)), "au total"),
                    ("Prêt", "Oui", "cliquez Rejouer"),
                ])
            with feed_slot.container():
                for d in alerts[:6]:
                    alert_card(d)

    with tab_quality:
        report = data_quality_report(transactions)
        kpi_strip([
            ("Complétude", f"{report['completeness']*100:.1f}%", "des champs"),
            ("Volume", str(report["total"]), "transactions"),
            ("Problèmes", str(len(report["issues"])), "types détectés"),
        ])
        st.write("")
        if report["issues"]:
            st.markdown("###### Problèmes de qualité détectés")
            st.dataframe(pd.DataFrame(report["issues"]),
                         use_container_width=True, hide_index=True)
        else:
            st.success("Aucun problème de qualité majeur.")
