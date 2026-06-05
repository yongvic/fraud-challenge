"""
Investigation approfondie — outils d'analyse pour comprendre une décision.

- Simulateur « Et si ? » : modifier une transaction et voir le verdict évoluer.
- Fiche client 360° : profil, habitudes, chronologie.
- Réseaux de fraude détectés (graphe).
- Comparaison avec un détecteur naïf (montre les faux positifs évités).
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from fraud_detection import (
    _parse_timestamp,
    build_client_profile,
    detect_fraud_naive,
)
from aegis.ui.components import alert_card, empty_state, fmt_date, page_header


def render(ctx) -> None:
    transactions = ctx["transactions"]
    decisions = ctx["decisions"]
    engine = ctx["engine"]

    page_header(
        "Investigation",
        "Atelier d'investigation",
        "Simulez, explorez le profil d'un client, visualisez les réseaux et "
        "comparez avec une approche naïve.",
    )

    tabs = st.tabs(["Simulateur Et si ?", "Fiche client 360°",
                    "Réseaux de fraude", "Comparaison naïf"])

    # ── Simulateur ─────────────────────────────────────────────────────
    with tabs[0]:
        ids = [t.get("transaction_id") for t in transactions]
        if not ids:
            empty_state("Aucune transaction", "Chargez des données.")
        else:
            pick = st.selectbox("Transaction de base", ids)
            base_idx = ids.index(pick)
            base = dict(transactions[base_idx])

            c1, c2, c3 = st.columns(3)
            sim_amount = c1.number_input("Montant", value=float(base.get("amount") or 0.0))
            sim_country = c2.text_input("Pays (ISO)", value=base.get("country") or "FR")
            sim_shift = c3.slider("Décalage horaire (h)", -72, 72, 0)

            base_dt = _parse_timestamp(base.get("timestamp"))
            if base_dt:
                sim_ts = (base_dt + timedelta(hours=sim_shift)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
            else:
                sim_ts = base.get("timestamp")

            sim_batch = list(transactions)
            sim_batch[base_idx] = {**base, "amount": sim_amount,
                                   "country": sim_country, "timestamp": sim_ts}
            sim_dec = engine.analyze(sim_batch)[base_idx]

            col_o, col_s = st.columns(2)
            with col_o:
                st.markdown("**Décision actuelle**")
                alert_card(decisions[base_idx])
            with col_s:
                st.markdown("**Décision simulée**")
                alert_card(sim_dec, focus=True)

    # ── Fiche client 360° ──────────────────────────────────────────────
    with tabs[1]:
        clients = sorted({t.get("user_id") for t in transactions if t.get("user_id")})
        if not clients:
            empty_state("Aucun client", "Chargez des données.")
        else:
            uid = st.selectbox("Client", clients)
            profile = build_client_profile(transactions, uid)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Opérations", profile["transaction_count"])
            med = profile["median_amount"]
            c2.metric("Dépense médiane", f"{med:,.0f}".replace(",", " ") if med else "—")
            c3.metric("Pays", len(profile["countries"]))
            c4.metric("Devises", len(profile["currencies"]))

            amounts = [t["amount"] for t in profile["timeline"]
                       if isinstance(t.get("amount"), (int, float))]
            if amounts:
                st.line_chart(pd.Series(amounts, name="Montant"))

            client_alerts = [d for d in decisions
                             if d.get("user_id") == uid and d["is_suspicious"]]
            if client_alerts:
                st.markdown("###### Alertes de ce client")
                for d in client_alerts:
                    alert_card(d)
            else:
                st.success("Aucune alerte pour ce client.")

            st.markdown("###### Chronologie")
            tl = pd.DataFrame(profile["timeline"])
            if not tl.empty:
                tl["Quand"] = tl["timestamp"].apply(fmt_date)
                st.dataframe(tl[["transaction_id", "Quand", "amount",
                             "country", "merchant"]],
                             use_container_width=True, hide_index=True)

    # ── Réseaux de fraude ──────────────────────────────────────────────
    with tabs[2]:
        rings = engine.last_rings
        if not rings:
            empty_state("Aucun réseau détecté",
                        "Aucun groupe de comptes liés au-delà du seuil.")
        else:
            st.caption("Comptes reliés par un même point de cashout (marchand + pays) "
                       "dans une fenêtre temporelle resserrée.")
            for r in rings:
                st.markdown(
                    f"<div class='ring-card'><div class='h'>Réseau de {r['size']} comptes "
                    f"· {r['merchant']} ({r['country']})</div>"
                    f"<div class='sub'>Membres : {', '.join(r['members'])}<br>"
                    f"Transactions : {', '.join(r['transactions'])}</div></div>",
                    unsafe_allow_html=True,
                )

    # ── Comparaison naïf ───────────────────────────────────────────────
    with tabs[3]:
        st.caption("Détecteur naïf : alerte sur tout changement de pays en moins de 3 h. "
                   "Aegis raisonne avec la distance réelle et évite les faux positifs.")
        naive = detect_fraud_naive(transactions)
        rows = []
        for i, d in enumerate(decisions):
            nav = naive[i]
            rows.append({
                "Transaction": d["transaction_id"],
                "Pays": d["country"],
                "Aegis": "Alerte" if d["is_suspicious"] else "OK",
                "Naïf (3h)": "Alerte" if nav["is_suspicious"] else "OK",
                "Écart": d["is_suspicious"] != nav["is_suspicious"],
            })
        cmp_df = pd.DataFrame(rows)
        diff = cmp_df[cmp_df["Écart"]]
        if not diff.empty:
            st.success(f"{len(diff)} cas où Aegis est plus précis que le détecteur naïf.")
            st.dataframe(diff, use_container_width=True, hide_index=True)
        st.dataframe(cmp_df, use_container_width=True, hide_index=True)
