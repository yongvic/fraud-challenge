"""
Design system Aegis — thèmes Clair & Sombre calibrés.

Principes (skill « impeccable », registre produit) :
- Neutres teintés vers la teinte de marque (jamais #000 / #fff purs).
- Un seul accent de marque (iris/indigo) ; le reste est neutre discipliné.
- Couleurs de risque sémantiques, calibrées par mode pour le contraste.
- Les badges de risque utilisent un fond teinté (pas un aplat criard).
- Échelle typographique à contraste de poids ; ombres discrètes en clair.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st

THEME_OPTIONS = ("Clair", "Sombre")

RISK_ORDER = ["Critique", "Élevé", "Modéré", "Sain"]


@dataclass(frozen=True)
class ThemeTokens:
    name: str
    bg: str
    surface: str
    surface_2: str
    sidebar: str
    ink: str
    body: str
    muted: str
    faint: str
    border: str
    border_soft: str
    accent: str
    accent_hover: str
    accent_fg: str
    track: str
    ring_bg: str
    ring_border: str
    empty_border: str
    shadow: str
    shadow_lg: str
    risk: dict = field(default_factory=dict)


# Couleurs de risque calibrées : variantes foncées en clair (lisibles comme
# texte), variantes claires en sombre (lisibles sur fond foncé).
_RISK_LIGHT = {
    "Critique": "#e11d48",
    "Élevé": "#c2620a",
    "Modéré": "#2563eb",
    "Sain": "#047857",
}
_RISK_DARK = {
    "Critique": "#fb7185",
    "Élevé": "#fbbf24",
    "Modéré": "#60a5fa",
    "Sain": "#34d399",
}


LIGHT = ThemeTokens(
    name="light",
    bg="#f5f5f8",
    surface="#fcfcfe",
    surface_2="#f0f0f5",
    sidebar="#fafafc",
    ink="#1a1a23",
    body="#3f3f4a",
    muted="#6b6b78",
    faint="#9a9aa6",
    border="#e6e6ee",
    border_soft="#f0f0f5",
    accent="#4f46e5",
    accent_hover="#4338ca",
    accent_fg="#ffffff",
    track="#e6e6ee",
    ring_bg="#fdf2f4",
    ring_border="#f6cdd6",
    empty_border="#d4d4de",
    shadow="0 1px 2px rgba(26,26,35,0.05), 0 1px 3px rgba(26,26,35,0.04)",
    shadow_lg="0 4px 16px rgba(26,26,35,0.08)",
    risk=_RISK_LIGHT,
)

DARK = ThemeTokens(
    name="dark",
    bg="#0b0b0f",
    surface="#141419",
    surface_2="#1b1b22",
    sidebar="#0e0e13",
    ink="#f7f7fa",
    body="#d4d4dd",
    muted="#9a9aa8",
    faint="#6b6b78",
    border="#27272f",
    border_soft="#1d1d24",
    accent="#818cf8",
    accent_hover="#a5b0fb",
    accent_fg="#0b0b0f",
    track="#27272f",
    ring_bg="#1a1014",
    ring_border="#4b2d36",
    empty_border="#2c2c34",
    shadow="none",
    shadow_lg="0 8px 28px rgba(0,0,0,0.45)",
    risk=_RISK_DARK,
)

# Rétrocompatibilité (graphiques Altair côté Python).
INK = DARK.ink
MUTED = DARK.muted
FAINT = DARK.faint
SURFACE = DARK.surface
BG = DARK.bg
BORDER = DARK.border
ACCENT = DARK.accent


def get_mode() -> str:
    return st.session_state.get("aegis_theme", "Clair")


def tokens(mode: str | None = None) -> ThemeTokens:
    return LIGHT if (mode or get_mode()) == "Clair" else DARK


def risk_color(level: str, mode: str | None = None) -> str:
    return tokens(mode).risk.get(level, tokens(mode).muted)


def _css(t: ThemeTokens) -> str:
    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

  :root {{
    --ag-bg:{t.bg}; --ag-surface:{t.surface}; --ag-surface-2:{t.surface_2};
    --ag-sidebar:{t.sidebar}; --ag-ink:{t.ink}; --ag-body:{t.body};
    --ag-muted:{t.muted}; --ag-faint:{t.faint}; --ag-border:{t.border};
    --ag-border-soft:{t.border_soft}; --ag-accent:{t.accent};
    --ag-accent-hover:{t.accent_hover}; --ag-accent-fg:{t.accent_fg};
    --ag-track:{t.track}; --ag-ring-bg:{t.ring_bg}; --ag-ring-border:{t.ring_border};
    --ag-empty-border:{t.empty_border}; --ag-shadow:{t.shadow}; --ag-shadow-lg:{t.shadow_lg};
  }}

  .stApp {{ background:var(--ag-bg) !important; }}
  html, body, [class*="css"], .stMarkdown, p, label, li {{
    font-family:'Plus Jakarta Sans', system-ui, sans-serif; color:var(--ag-body);
    -webkit-font-smoothing:antialiased;
  }}
  .block-container {{ padding-top:1.5rem; max-width:1280px; }}
  .mono {{ font-family:'JetBrains Mono', monospace; font-variant-numeric:tabular-nums; }}
  h1,h2,h3,h4,h5,h6 {{ color:var(--ag-ink); letter-spacing:-0.02em; }}
  strong, b {{ color:var(--ag-ink); }}
  a {{ color:var(--ag-accent); }}

  /* Sidebar */
  [data-testid="stSidebar"] {{
    background:var(--ag-sidebar) !important; border-right:1px solid var(--ag-border);
  }}
  [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{ color:var(--ag-body) !important; }}

  /* Captions */
  .stCaption, small, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
    color:var(--ag-muted) !important; font-size:.74rem; letter-spacing:.06em; font-weight:600;
  }}

  /* Inputs */
  .stTextInput input, .stNumberInput input,
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {{
    background:var(--ag-surface) !important; color:var(--ag-ink) !important;
    border-color:var(--ag-border) !important; border-radius:10px !important;
  }}
  .stTextInput input::placeholder {{ color:var(--ag-faint) !important; }}

  /* Boutons */
  .stButton > button {{
    background:var(--ag-surface) !important; color:var(--ag-ink) !important;
    border:1px solid var(--ag-border) !important; border-radius:10px !important;
    font-weight:600 !important; transition:border-color .15s, background .15s;
  }}
  .stButton > button:hover {{ border-color:var(--ag-accent) !important; }}
  .stButton > button[kind="primary"], .stButton > button[data-testid="baseButton-primary"] {{
    background:var(--ag-accent) !important; color:var(--ag-accent-fg) !important;
    border-color:var(--ag-accent) !important;
  }}
  .stButton > button[kind="primary"]:hover {{ background:var(--ag-accent-hover) !important; }}
  .stDownloadButton > button {{
    background:var(--ag-accent) !important; color:var(--ag-accent-fg) !important;
    border:1px solid var(--ag-accent) !important; border-radius:10px !important; font-weight:600 !important;
  }}

  /* Onglets */
  .stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid var(--ag-border); }}
  .stTabs [data-baseweb="tab"] {{
    background:transparent !important; color:var(--ag-muted) !important;
    border:none !important; border-radius:8px 8px 0 0 !important; padding:6px 14px !important;
  }}
  .stTabs [aria-selected="true"] {{
    color:var(--ag-ink) !important; font-weight:700 !important;
    border-bottom:2px solid var(--ag-accent) !important;
  }}

  /* Métriques natives */
  [data-testid="stMetric"] {{
    background:var(--ag-surface); border:1px solid var(--ag-border);
    border-radius:14px; padding:14px 16px; box-shadow:var(--ag-shadow);
  }}
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{ color:var(--ag-muted) !important; }}
  [data-testid="stMetricValue"] {{ color:var(--ag-ink) !important; font-weight:700; }}

  /* Tables */
  [data-testid="stDataFrame"] {{ border:1px solid var(--ag-border); border-radius:12px; overflow:hidden; }}
  hr {{ border-color:var(--ag-border) !important; }}
  .stAlert {{ border-radius:12px !important; }}

  /* ── Composants Aegis ── */
  .ag-brand {{ display:flex; align-items:center; gap:11px; }}
  .ag-logo {{
    width:34px; height:34px; border-radius:9px; background:var(--ag-accent);
    display:grid; place-items:center; color:var(--ag-accent-fg); font-weight:800; font-size:1.05rem;
    box-shadow:var(--ag-shadow);
  }}
  .ag-name {{ font-weight:800; color:var(--ag-ink); font-size:1.1rem; letter-spacing:-0.02em; line-height:1.1; }}
  .ag-tag {{ color:var(--ag-faint); font-size:.7rem; letter-spacing:.04em; }}

  .eyebrow {{ color:var(--ag-accent); font-size:.7rem; font-weight:700;
    letter-spacing:.16em; text-transform:uppercase; }}
  .page-title {{ font-size:1.6rem; font-weight:800; color:var(--ag-ink);
    letter-spacing:-0.03em; margin:.15rem 0 .1rem; }}
  .page-sub {{ color:var(--ag-muted); font-size:.93rem; max-width:68ch;
    margin-bottom:.4rem; line-height:1.55; font-weight:500; }}

  .summary {{
    border:1px solid var(--ag-border); background:var(--ag-surface); border-radius:14px;
    padding:16px 19px; margin:12px 0; color:var(--ag-body); line-height:1.6;
    box-shadow:var(--ag-shadow); font-size:.92rem;
  }}
  .summary b {{ color:var(--ag-ink); }}

  .kpi-strip {{
    display:grid; grid-template-columns:repeat(var(--n,4),1fr);
    border:1px solid var(--ag-border); border-radius:16px; overflow:hidden;
    background:var(--ag-surface); box-shadow:var(--ag-shadow);
  }}
  .kpi {{ padding:16px 19px; border-right:1px solid var(--ag-border); }}
  .kpi:last-child {{ border-right:none; }}
  .kpi .lbl {{ color:var(--ag-muted); font-size:.7rem; font-weight:700;
    text-transform:uppercase; letter-spacing:.07em; }}
  .kpi .val {{ font-size:1.75rem; font-weight:800; color:var(--ag-ink); margin-top:5px; letter-spacing:-0.02em; }}
  .kpi .hint {{ color:var(--ag-faint); font-size:.76rem; margin-top:3px; font-weight:500; }}

  .alert {{
    border:1px solid var(--ag-border); background:var(--ag-surface);
    border-radius:14px; padding:15px 18px; margin-bottom:11px; box-shadow:var(--ag-shadow);
  }}
  .alert.focus {{ border-color:var(--ag-accent); box-shadow:0 0 0 3px var(--accent-ring,rgba(99,102,241,.18)); }}
  .alert-top {{ display:flex; align-items:center; gap:10px; }}
  .dot {{ width:8px; height:8px; border-radius:50%; background:var(--c); flex:0 0 auto; }}
  .tid {{ font-weight:800; color:var(--ag-ink); font-size:1rem; letter-spacing:-0.01em; }}
  .chip {{
    font-size:.72rem; font-weight:700; color:var(--c);
    background:color-mix(in srgb, var(--c) 14%, transparent);
    border:1px solid color-mix(in srgb, var(--c) 35%, transparent);
    padding:3px 10px; border-radius:8px; white-space:nowrap;
  }}
  .codes {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
  .code {{
    font-size:.7rem; color:var(--ag-muted); background:var(--ag-surface-2);
    border:1px solid var(--ag-border); padding:3px 9px; border-radius:7px; font-weight:600;
  }}
  .reason {{ color:var(--ag-ink); font-weight:700; margin:9px 0 3px; font-size:.95rem; }}
  .meta {{ color:var(--ag-muted); font-size:.83rem; font-weight:500; }}
  .meta b {{ color:var(--ag-body); font-weight:700; }}

  .layer-bars {{ display:grid; gap:8px; margin-top:11px; padding-top:11px; border-top:1px solid var(--ag-border); }}
  .layer {{ display:flex; align-items:center; gap:11px; }}
  .layer .lname {{ width:108px; color:var(--ag-muted); font-size:.76rem; font-weight:600; }}
  .layer .track {{ flex:1; height:6px; border-radius:999px; background:var(--ag-track); overflow:hidden; }}
  .layer .fill {{ height:100%; border-radius:999px; }}
  .layer .lval {{ width:38px; text-align:right; color:var(--ag-ink); font-size:.76rem; font-weight:700; }}

  .panel {{
    border:1px solid var(--ag-border); background:var(--ag-surface);
    border-radius:14px; padding:17px 19px; box-shadow:var(--ag-shadow);
  }}
  .empty {{
    border:1px dashed var(--ag-empty-border); border-radius:14px; padding:42px 22px;
    text-align:center; color:var(--ag-muted); background:var(--ag-surface);
  }}
  .empty .big {{ color:var(--ag-ink); font-weight:700; font-size:1.05rem; margin-bottom:5px; }}

  .ring-card {{
    border:1px solid var(--ag-ring-border); background:var(--ag-ring-bg);
    border-radius:13px; padding:15px 17px; margin-bottom:10px; box-shadow:var(--ag-shadow);
  }}
  .ring-card .h {{ color:var(--ag-ink); font-weight:800; }}
  .ring-card .sub {{ color:var(--ag-muted); font-size:.85rem; margin-top:5px; line-height:1.5; }}

  /* Email / communications preview */
  .mail {{
    border:1px solid var(--ag-border); border-radius:14px; overflow:hidden;
    box-shadow:var(--ag-shadow-lg); background:var(--ag-surface); margin-top:6px;
  }}
  .mail-bar {{ display:flex; align-items:center; gap:7px; padding:10px 14px;
    background:var(--ag-surface-2); border-bottom:1px solid var(--ag-border); }}
  .mail-dot {{ width:10px; height:10px; border-radius:50%; }}
  .mail-head {{ padding:14px 18px 6px; border-bottom:1px solid var(--ag-border-soft); }}
  .mail-subj {{ color:var(--ag-ink); font-weight:800; font-size:1.02rem; letter-spacing:-0.01em; }}
  .mail-from {{ color:var(--ag-muted); font-size:.8rem; margin-top:3px; }}
  .mail-body {{ padding:16px 18px; color:var(--ag-body); line-height:1.65; font-size:.9rem; }}
  .mail-body b {{ color:var(--ag-ink); }}
  .mail-btn {{ display:inline-block; margin-top:6px; padding:9px 16px; border-radius:9px;
    background:var(--ag-accent); color:var(--ag-accent-fg); font-weight:700; font-size:.85rem; }}
  .mail-fine {{ color:var(--ag-faint); font-size:.75rem; margin-top:14px;
    border-top:1px solid var(--ag-border-soft); padding-top:10px; line-height:1.5; }}

  .timeline {{ border-left:2px solid var(--ag-border); margin-left:6px; padding-left:16px; }}
  .tl-item {{ position:relative; padding:6px 0 12px; }}
  .tl-item::before {{ content:''; position:absolute; left:-23px; top:9px; width:9px; height:9px;
    border-radius:50%; background:var(--ag-accent); box-shadow:0 0 0 3px var(--ag-bg); }}
  .tl-when {{ color:var(--ag-faint); font-size:.74rem; font-weight:600; }}
  .tl-what {{ color:var(--ag-ink); font-weight:600; font-size:.9rem; }}
  .tl-detail {{ color:var(--ag-muted); font-size:.82rem; }}

  @media (max-width:980px) {{ .kpi-strip {{ grid-template-columns:1fr 1fr; }} }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>
"""


def inject(mode: str | None = None) -> None:
    st.markdown(_css(tokens(mode)), unsafe_allow_html=True)


def style_chart(chart, mode: str | None = None):
    """Couleurs d'axes/légende Altair selon le thème."""
    t = tokens(mode)
    return (
        chart.configure_view(stroke=None, fill="transparent")
        .configure_axis(labelColor=t.muted, titleColor=t.muted,
                        gridColor=t.border, domainColor=t.border)
        .configure_legend(labelColor=t.body, titleColor=t.ink)
    )


def theme_selector() -> str:
    st.caption("APPARENCE")
    return st.radio(
        "Thème", THEME_OPTIONS,
        index=0 if get_mode() == "Clair" else 1,
        label_visibility="collapsed", key="aegis_theme", horizontal=True,
    )


def brand_header() -> None:
    st.markdown(
        "<div class='ag-brand'><div class='ag-logo'>A</div>"
        "<div><div class='ag-name'>Aegis</div>"
        "<div class='ag-tag'>FINANCIAL CRIME INTELLIGENCE</div></div></div>",
        unsafe_allow_html=True,
    )
