"""
Console Analyste — le poste de travail quotidien d'un enquêteur fraude.

File d'investigation priorisée par risque, avec actions de traitement
(assignation, confirmer la fraude, classer en faux positif). Chaque action
crée/alimente un dossier et est journalisée dans la piste d'audit. C'est ici que
naît la boucle de feedback.
"""

from __future__ import annotations

import streamlit as st

from aegis.casemgmt import CASE_STATUSES
from aegis.comms import audit_artifact
from aegis.ui.components import alert_card, empty_state, kpi_strip, page_header


def render(ctx) -> None:
    decisions = ctx["decisions"]
    store = ctx["store"]
    df = ctx["df"]

    page_header(
        "Opérations",
        "Console Analyste",
        "File d'investigation priorisée par le risque. Traitez chaque alerte : "
        "assignez, confirmez la fraude ou classez en faux positif.",
    )

    alerts = [d for d in decisions if d["is_suspicious"]]
    store.sync_alerts(decisions, actor="system")
    metrics = store.feedback_metrics()

    kpi_strip([
        ("Alertes ouvertes", str(len(alerts)), "à traiter"),
        ("Dossiers", str(metrics["total_cases"]), "suivis"),
        ("Résolus", str(metrics["resolved"]), "tranchés"),
        ("Précision", f"{metrics['precision']*100:.0f}%" if metrics["precision"] is not None else "—",
         "sur dossiers résolus"),
    ])
    st.write("")

    # Filtres.
    c1, c2, c3 = st.columns([1.2, 1, 1])
    search = c1.text_input("Recherche", placeholder="ID transaction ou client…",
                           label_visibility="collapsed")
    levels = c2.multiselect("Niveaux", ["Critique", "Élevé", "Modéré"],
                            default=["Critique", "Élevé", "Modéré"],
                            label_visibility="collapsed", placeholder="Niveaux")
    status_filter = c3.selectbox("Statut", ["Tous"] + CASE_STATUSES,
                                 label_visibility="collapsed")

    cases_by_id = {c["transaction_id"]: c for c in store.list_cases()}

    view = [d for d in alerts if d["level"] in levels]
    if search:
        s = search.lower()
        view = [d for d in view
                if s in str(d["transaction_id"]).lower()
                or s in str(d.get("user_id") or "").lower()
                or s in str(d.get("user_masked") or "").lower()]
    if status_filter != "Tous":
        view = [d for d in view
                if cases_by_id.get(d["transaction_id"], {}).get("status") == status_filter]
    view.sort(key=lambda d: d["fraud_score"], reverse=True)

    if not view:
        empty_state("Aucune alerte à traiter",
                    "Ajustez les filtres ou consultez la supervision temps réel.")
        return

    for d in view:
        case = cases_by_id.get(d["transaction_id"], {})
        status = case.get("status", "Nouveau")
        col_card, col_actions = st.columns([2.4, 1])
        with col_card:
            alert_card(d)
        with col_actions:
            st.markdown(f"**Statut :** {status}")
            if case.get("assignee"):
                st.caption(f"Assigné à {case['assignee']}")
            analyst = st.session_state.get("current_user", "Analyste")
            tid = d["transaction_id"]
            b1, b2 = st.columns(2)
            if b1.button("Fraude", key=f"fraud_{tid}", use_container_width=True):
                store.update_status(tid, "Fraude confirmée", analyst,
                                    "Confirmé depuis la console")
                st.rerun()
            if b2.button("Légitime", key=f"legit_{tid}", use_container_width=True):
                store.update_status(tid, "Faux positif", analyst,
                                    "Classé légitime")
                st.rerun()
            if st.button("Prendre en charge", key=f"take_{tid}",
                         use_container_width=True):
                store.assign(tid, analyst, analyst)
                store.update_status(tid, "En investigation", analyst)
                st.rerun()
            artifact = audit_artifact(d, case)
            if st.download_button("Rapport d'audit", data=artifact["data"],
                                  file_name=artifact["filename"],
                                  mime=artifact["mime"], key=f"audit_{tid}",
                                  use_container_width=True):
                store.log_communication(tid, "PDF audit", d["user_masked"],
                                        f"Rapport d'audit {tid}", actor=analyst)
        st.divider()
