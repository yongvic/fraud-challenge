"""
Démo jury — parcours guidé qui raconte l'histoire d'Aegis en 4 actes.

Pensé pour une présentation : chaque acte met en avant une capacité distincte
(coeur deterministe, ML, graphe, opérationnel) avec un exemple concret tiré du
jeu de données.
"""

from __future__ import annotations

import streamlit as st

from aegis.ui.components import alert_card, empty_state, kpi_strip, page_header


def _find(decisions, predicate):
    for d in decisions:
        if predicate(d):
            return d
    return None


def render(ctx) -> None:
    decisions = ctx["decisions"]
    engine = ctx["engine"]

    page_header(
        "Présentation",
        "Démo guidée",
        "Quatre actes pour comprendre Aegis : des règles auditables au réseau de "
        "fraude, jusqu'au pilotage opérationnel.",
    )

    alerts = [d for d in decisions if d["is_suspicious"]]
    kpi_strip([
        ("Transactions", str(len(decisions)), "analysées"),
        ("Alertes", str(len(alerts)), "remontées"),
        ("Réseaux", str(len(engine.last_rings)), "détectés"),
        ("Moteur ML", engine.ml_backend.replace("_", " "), "anomalie"),
    ])
    st.write("")

    st.markdown("#### Acte 1 — Le coeur deterministe (voyage impossible)")
    st.markdown(
        "<div class='summary'>Aegis calcule la <b>distance géographique réelle</b> "
        "entre deux opérations. Payer à Paris puis au Japon en 40 minutes est "
        "<b>physiquement impossible</b> : la règle est explicable et reproductible "
        "(exigence réglementaire).</div>", unsafe_allow_html=True)
    geo = _find(decisions, lambda d: "RULE_GEO" in d["reason_codes"])
    if geo:
        alert_card(geo, focus=True)
    else:
        empty_state("Pas d'exemple de voyage impossible", "dans ce jeu de données.")

    st.markdown("#### Acte 2 — L'augmentation ML (anomalie comportementale)")
    st.markdown(
        "<div class='summary'>Au-delà des règles, un modèle <b>non supervisé</b> "
        "apprend la normalité de chaque client et signale l'atypique — une dépense "
        "nocturne, carte absente, très au-dessus des habitudes.</div>",
        unsafe_allow_html=True)
    ml = _find(decisions, lambda d: "ML_ANOMALY" in d["reason_codes"]
               and "RULE_GEO" not in d["reason_codes"])
    if ml:
        alert_card(ml, focus=True)
    else:
        empty_state("Pas d'exemple ML isolé", "dans ce jeu de données.")

    st.markdown("#### Acte 3 — Le graphe (réseau de fraude)")
    st.markdown(
        "<div class='summary'>Les fraudeurs opèrent en réseau. Aegis relie les "
        "comptes partageant un même point de cashout et révèle des <b>anneaux de "
        "fraude</b> invisibles transaction par transaction.</div>",
        unsafe_allow_html=True)
    if engine.last_rings:
        r = engine.last_rings[0]
        st.markdown(
            f"<div class='ring-card'><div class='h'>Réseau de {r['size']} comptes "
            f"· {r['merchant']} ({r['country']})</div>"
            f"<div style='color:#a1a1aa;font-size:.85rem;margin-top:4px'>"
            f"Membres : {', '.join(r['members'])}</div></div>",
            unsafe_allow_html=True)
        ring = _find(decisions, lambda d: "GRAPH_RING" in d["reason_codes"])
        if ring:
            alert_card(ring, focus=True)
    else:
        empty_state("Aucun réseau détecté", "dans ce jeu de données.")

    st.markdown("#### Acte 4 — L'humain dans la boucle")
    st.markdown(
        "<div class='summary'>Chaque alerte devient un <b>dossier</b> tracé. "
        "L'analyste tranche (fraude / faux positif), la décision est <b>auditée</b>, "
        "et alimente une <b>boucle de feedback</b> qui mesure la précision du système. "
        "Rendez-vous dans la Console Analyste pour traiter une alerte.</div>",
        unsafe_allow_html=True)
