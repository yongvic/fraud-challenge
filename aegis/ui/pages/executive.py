"""
Direction (Executive) — la vue pilotage pour un comité de direction.

KPIs métier : exposition financière, pertes potentiellement évitées, taux de
détection et de faux positifs, répartition du risque par pays et par motif.
Langage business, pas technique.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from aegis.config import CONFIG, RISK_COLORS
from aegis.ui.components import kpi_strip, page_header


def render(ctx) -> None:
    decisions = ctx["decisions"]
    df = ctx["df"]
    cfg = CONFIG

    page_header(
        "Pilotage",
        "Tableau de bord Direction",
        "Vision consolidée du risque de fraude : exposition, pertes évitées et "
        "qualité de détection, en langage métier.",
    )

    total = len(df)
    alerts = int(df["Suspecte"].sum()) if total else 0
    amount_at_risk = df.loc[df["Suspecte"], "Montant"].apply(
        lambda x: x if isinstance(x, (int, float)) and x > 0 else 0).sum()
    losses_avoided = amount_at_risk * cfg.assumed_loss_recovery_rate
    rate = (alerts / total * 100) if total else 0.0

    kpi_strip([
        ("Transactions", str(total), "sur la période"),
        ("Exposition à risque", f"{amount_at_risk:,.0f}".replace(",", " "),
         f"en {cfg.base_currency}"),
        ("Pertes évitées (est.)", f"{losses_avoided:,.0f}".replace(",", " "),
         f"hyp. {cfg.assumed_loss_recovery_rate*100:.0f}% recouvrement"),
        ("Taux d'alerte", f"{rate:.0f}%", "des opérations"),
    ])
    st.write("")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("###### Risque par motif")
        flagged = df[df["Suspecte"]]
        if len(flagged):
            counts = flagged["Motif"].value_counts().reset_index()
            counts.columns = ["Motif", "Nombre"]
            chart = (
                alt.Chart(counts).mark_bar(cornerRadius=4, color="#fbbf24")
                .encode(
                    x=alt.X("Nombre:Q", title=None),
                    y=alt.Y("Motif:N", sort="-x", title=None),
                    tooltip=["Motif", "Nombre"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.caption("Aucune alerte.")

    with col_b:
        st.markdown("###### Exposition par pays")
        flagged = df[df["Suspecte"]].copy()
        flagged["Montant"] = flagged["Montant"].apply(
            lambda x: x if isinstance(x, (int, float)) and x > 0 else 0)
        if len(flagged):
            by_country = (flagged.groupby("Pays")["Montant"].sum()
                          .reset_index().sort_values("Montant", ascending=False))
            chart = (
                alt.Chart(by_country).mark_bar(cornerRadius=4, color="#fb7185")
                .encode(
                    x=alt.X("Montant:Q", title=None),
                    y=alt.Y("Pays:N", sort="-x", title=None),
                    tooltip=["Pays", "Montant"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.caption("Aucune exposition.")

    st.markdown("###### Répartition par niveau de risque")
    level_counts = df["Niveau"].value_counts().reindex(
        ["Critique", "Élevé", "Modéré", "Sain"]).fillna(0).reset_index()
    level_counts.columns = ["Niveau", "Nombre"]
    domain = ["Critique", "Élevé", "Modéré", "Sain"]
    rng = [RISK_COLORS[k] for k in domain]
    chart = (
        alt.Chart(level_counts).mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("Niveau:N", sort=domain, title=None),
            y=alt.Y("Nombre:Q", title=None),
            color=alt.Color("Niveau:N", scale=alt.Scale(domain=domain, range=rng),
                            legend=None),
            tooltip=["Niveau", "Nombre"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, use_container_width=True)
