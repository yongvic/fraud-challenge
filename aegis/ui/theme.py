"""
Design system d'Aegis (skill « impeccable »).

Un seul fichier de style, des tokens cohérents, une palette neutre disciplinée
plus des couleurs sémantiques de risque. Aucun anti-pattern (pas de bordure
latérale colorée, pas de texte en dégradé, pas de glow décoratif). Contraste
vérifié pour la lisibilité. Typographie : Plus Jakarta Sans (texte) + JetBrains
Mono (chiffres).
"""

from __future__ import annotations

import streamlit as st

# Tokens (référencés aussi côté Python pour les graphiques).
INK = "#fafafa"
MUTED = "#a1a1aa"
FAINT = "#71717a"
SURFACE = "#131316"
SURFACE_2 = "#17171b"
BG = "#0a0a0b"
BORDER = "#26262b"
ACCENT = "#34d399"

CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

  .stApp {{ background: {BG}; }}
  html, body, [class*="css"], .stMarkdown {{
    font-family: 'Plus Jakarta Sans', system-ui, sans-serif; color: #e4e4e7;
  }}
  .block-container {{ padding-top: 1.6rem; max-width: 1320px; }}
  [data-testid="stSidebar"] {{ background: #0e0e10; border-right: 1px solid #1f1f23; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }}

  .ag-brand {{ display:flex; align-items:center; gap:10px; }}
  .ag-logo {{ width:30px; height:30px; border-radius:8px; background:{ACCENT};
    display:grid; place-items:center; color:{BG}; font-weight:800; font-size:1rem; }}
  .ag-name {{ font-weight:800; color:{INK}; font-size:1.05rem; letter-spacing:-0.01em; }}
  .ag-tag {{ color:{FAINT}; font-size:.72rem; }}

  .page-title {{ font-size:1.55rem; font-weight:800; color:{INK};
    letter-spacing:-0.02em; margin:.1rem 0 .1rem; }}
  .page-sub {{ color:{MUTED}; font-size:.92rem; max-width:70ch; margin-bottom:.6rem; }}
  .eyebrow {{ color:{FAINT}; font-size:.72rem; font-weight:600; letter-spacing:.14em;
    text-transform:uppercase; }}

  .summary {{ border:1px solid {BORDER}; background:{SURFACE}; border-radius:14px;
    padding:15px 18px; margin:12px 0; color:#d4d4d8; line-height:1.55; }}
  .summary b {{ color:{INK}; }}

  .kpi-strip {{ display:grid; grid-template-columns:repeat(var(--n,4),1fr);
    border:1px solid {BORDER}; border-radius:14px; overflow:hidden; background:{SURFACE}; }}
  .kpi {{ padding:15px 18px; border-right:1px solid {BORDER}; }}
  .kpi:last-child {{ border-right:none; }}
  .kpi .lbl {{ color:#8b8b93; font-size:.72rem; font-weight:600; text-transform:uppercase;
    letter-spacing:.03em; }}
  .kpi .val {{ font-size:1.7rem; font-weight:700; color:{INK}; margin-top:4px; }}
  .kpi .hint {{ color:{FAINT}; font-size:.76rem; margin-top:2px; }}

  .alert {{ border:1px solid var(--edge); background:var(--bg); border-radius:14px;
    padding:15px 18px; margin-bottom:11px; }}
  .alert.focus {{ outline:2px solid {ACCENT}; outline-offset:2px; }}
  .alert-top {{ display:flex; align-items:center; gap:10px; }}
  .dot {{ width:9px; height:9px; border-radius:50%; background:var(--c); flex:0 0 auto; }}
  .tid {{ font-weight:700; color:{INK}; font-size:1rem; }}
  .chip {{ font-size:.72rem; font-weight:700; color:{BG}; background:var(--c);
    padding:3px 10px; border-radius:999px; white-space:nowrap; }}
  .codes {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
  .code {{ font-size:.7rem; color:#d4d4d8; background:{SURFACE_2}; border:1px solid {BORDER};
    padding:2px 8px; border-radius:6px; }}
  .reason {{ color:{INK}; font-weight:600; margin:8px 0 2px; }}
  .meta {{ color:{MUTED}; font-size:.84rem; }}
  .why {{ color:{MUTED}; font-size:.84rem; margin-top:9px; border-top:1px solid {BORDER};
    padding-top:9px; line-height:1.5; }}

  .layer-bars {{ display:grid; gap:7px; margin-top:6px; }}
  .layer {{ display:flex; align-items:center; gap:10px; }}
  .layer .lname {{ width:120px; color:{MUTED}; font-size:.78rem; }}
  .layer .track {{ flex:1; height:7px; border-radius:999px; background:{BORDER}; overflow:hidden; }}
  .layer .fill {{ height:100%; border-radius:999px; }}
  .layer .lval {{ width:42px; text-align:right; color:{INK}; font-size:.78rem; }}

  .panel {{ border:1px solid {BORDER}; background:{SURFACE}; border-radius:14px; padding:16px 18px; }}
  .empty {{ border:1px dashed #2a2a30; border-radius:14px; padding:40px 22px;
    text-align:center; color:{MUTED}; }}
  .empty .big {{ color:{INK}; font-weight:700; font-size:1.08rem; margin-bottom:4px; }}

  .ring-card {{ border:1px solid #4b2d36; background:#1a1013; border-radius:12px;
    padding:14px 16px; margin-bottom:10px; }}
  .ring-card .h {{ color:{INK}; font-weight:700; }}

  @media (max-width: 980px) {{ .kpi-strip {{ grid-template-columns:1fr 1fr; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style>
"""


def inject() -> None:
    """Injecte le design system (idempotent par page)."""
    st.markdown(CSS, unsafe_allow_html=True)


def brand_header() -> None:
    st.markdown(
        "<div class='ag-brand'><div class='ag-logo'>A</div>"
        "<div><div class='ag-name'>Aegis</div>"
        "<div class='ag-tag'>Financial Crime Intelligence</div></div></div>",
        unsafe_allow_html=True,
    )
