"""
Rapport d'audit d'une décision (PDF si reportlab dispo, sinon HTML imprimable).

Le document est lisible par un non-technicien : motif en clair, décomposition
des couches, reason codes traduits, et traçabilité de la décision humaine.
C'est la matérialisation du droit à l'explication (RGPD) et de la diligence
(AML / LCB-FT).
"""

from __future__ import annotations

from datetime import datetime, timezone

from aegis.config import CONFIG
from aegis.data.ingest import mask_id
from aegis.engine.orchestrator import REASON_CODE_LABELS

try:  # dépendance optionnelle
    from reportlab.lib import colors  # type: ignore
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import (  # type: ignore
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
    import io
    _HAS_REPORTLAB = True
except Exception:  # pragma: no cover
    _HAS_REPORTLAB = False


def _doc_ref(transaction_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"AUD-{stamp}-{transaction_id}"


def _fmt_amount(amount, currency) -> str:
    if not isinstance(amount, (int, float)):
        return "—"
    txt = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} {currency or CONFIG.base_currency}".strip()


def _rows(decision: dict, case: dict | None) -> list[tuple[str, str]]:
    case = case or {}
    codes = decision.get("reason_codes", [])
    code_labels = "; ".join(REASON_CODE_LABELS.get(c, c) for c in codes) or "—"
    return [
        ("Référence du document", _doc_ref(decision.get("transaction_id", "?"))),
        ("Transaction", decision.get("transaction_id", "—")),
        ("Client (pseudonymisé)", mask_id(decision.get("user_id"))),
        ("Montant", _fmt_amount(decision.get("amount"), decision.get("currency"))),
        ("Commerçant", decision.get("merchant") or "—"),
        ("Pays", decision.get("country") or "—"),
        ("Horodatage opération", decision.get("timestamp") or "—"),
        ("Niveau de risque", decision.get("level", "—")),
        ("Score global", f"{decision.get('fraud_score', 0):.2f} / 1.00"),
        ("Couche règles", f"{decision.get('rule_score', 0):.2f}"),
        ("Couche ML (anomalie)", f"{decision.get('ml_score', 0):.2f}"),
        ("Couche réseau (graphe)", f"{decision.get('ring_score', 0):.2f}"),
        ("Motif principal", decision.get("reason", "—")),
        ("Reason codes", code_labels),
        ("Statut du dossier", case.get("status", "Nouveau")),
        ("Analyste assigné", case.get("assignee") or "Non assigné"),
    ]


def build_audit_html(decision: dict, case: dict | None = None) -> str:
    """Document HTML autonome et imprimable (toujours disponible)."""
    rows = _rows(decision, case)
    body_rows = "".join(
        f"<tr><td class='k'>{k}</td><td class='v'>{v}</td></tr>" for k, v in rows
    )
    generated = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport d'audit {decision.get('transaction_id')}</title>
<style>
  @page {{ margin:18mm; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; color:#1a1a23; margin:0; padding:32px;
    background:#fff; }}
  .head {{ display:flex; align-items:center; gap:12px; border-bottom:3px solid #4f46e5;
    padding-bottom:16px; margin-bottom:8px; }}
  .logo {{ width:40px; height:40px; border-radius:9px; background:#4f46e5; color:#fff;
    display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.3rem; }}
  .brand {{ font-size:1.35rem; font-weight:800; letter-spacing:-0.02em; }}
  .sub {{ color:#6b6b78; font-size:.8rem; }}
  h1 {{ font-size:1.05rem; margin:22px 0 4px; letter-spacing:-0.01em; }}
  .meta {{ color:#6b6b78; font-size:.78rem; margin-bottom:14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
  td {{ padding:9px 12px; border-bottom:1px solid #e6e6ee; vertical-align:top; }}
  td.k {{ color:#6b6b78; font-weight:600; width:40%; }}
  td.v {{ color:#1a1a23; font-weight:500; }}
  .legal {{ margin-top:22px; padding-top:14px; border-top:1px solid #e6e6ee;
    color:#9a9aa6; font-size:.72rem; line-height:1.55; }}
</style></head><body>
  <div class="head"><div class="logo">A</div>
    <div><div class="brand">{CONFIG.product_name}</div>
    <div class="sub">Rapport d'audit de décision · {CONFIG.organization}</div></div></div>
  <h1>Synthèse de la décision</h1>
  <div class="meta">Généré le {generated} · Document confidentiel</div>
  <table><tbody>{body_rows}</tbody></table>
  <div class="legal">
    Ce document est établi conformément au droit à l'explication (RGPD art. 22)
    et aux obligations de diligence en matière de lutte contre le blanchiment
    (LCB-FT / AML-CFT). Les identifiants clients sont pseudonymisés. La décision
    finale relève d'un analyste habilité ; la piste d'audit complète est
    conservée de façon immuable dans le système {CONFIG.product_name}.
  </div>
</body></html>"""


def build_audit_pdf(decision: dict, case: dict | None = None) -> bytes | None:
    """PDF via reportlab. None si la librairie n'est pas installée."""
    if not _HAS_REPORTLAB:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm,
                            bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    accent = colors.HexColor("#4f46e5")
    ink = colors.HexColor("#1a1a23")
    muted = colors.HexColor("#6b6b78")

    title = ParagraphStyle("t", parent=styles["Title"], textColor=ink,
                           fontSize=18, spaceAfter=2, alignment=0)
    sub = ParagraphStyle("s", parent=styles["Normal"], textColor=muted, fontSize=9)
    h1 = ParagraphStyle("h1", parent=styles["Heading2"], textColor=ink, fontSize=12)
    legal = ParagraphStyle("l", parent=styles["Normal"], textColor=muted,
                           fontSize=7.5, leading=11)

    story = [
        Paragraph(f"{CONFIG.product_name}", title),
        Paragraph(f"Rapport d'audit de décision · {CONFIG.organization}", sub),
        Spacer(1, 14),
        Paragraph("Synthèse de la décision", h1),
        Paragraph("Généré le "
                  + datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
                  + " · Document confidentiel", sub),
        Spacer(1, 10),
    ]

    data = [[k, str(v)] for k, v in _rows(decision, case)]
    table = Table(data, colWidths=[68 * mm, 104 * mm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("TEXTCOLOR", (1, 0), (1, -1), ink),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e6e6ee")),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Ce document est établi conformément au droit à l'explication "
        "(RGPD art. 22) et aux obligations de diligence (LCB-FT / AML-CFT). "
        "Les identifiants clients sont pseudonymisés. La décision finale relève "
        "d'un analyste habilité ; la piste d'audit complète est conservée de "
        f"façon immuable dans le système {CONFIG.product_name}.", legal))

    doc.build(story)
    return buf.getvalue()


def audit_artifact(decision: dict, case: dict | None = None) -> dict:
    """Renvoie le meilleur artefact disponible (PDF sinon HTML imprimable)."""
    tid = decision.get("transaction_id", "audit")
    pdf = build_audit_pdf(decision, case)
    if pdf is not None:
        return {"data": pdf, "mime": "application/pdf",
                "filename": f"aegis_audit_{tid}.pdf", "kind": "PDF"}
    html = build_audit_html(decision, case).encode("utf-8")
    return {"data": html, "mime": "text/html",
            "filename": f"aegis_audit_{tid}.html", "kind": "HTML imprimable"}
