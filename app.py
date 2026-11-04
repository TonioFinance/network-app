"""NETWORK : carnet de réseau (pros, étudiants, alumni). Saisie rapide sur téléphone, données dans un Google Sheet.

Secrets Streamlit (.streamlit/secrets.toml en local, ou « Secrets » sur Streamlit Community Cloud) :
    app_password = "..."                 # mot de passe d'accès (conseillé)
    network_sheet_id = "..."             # identifiant du Google Sheet (dans son adresse, entre /d/ et /edit)
    [gcp_service_account]                # le même compte de service que l'app Budget
    type = "service_account"
    ...
Sans [gcp_service_account], l'app tourne en local sur un fichier CSV (network_local.csv) : pratique pour essayer.
"""
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import network_core as nc

st.set_page_config(page_title="Network", page_icon="🤝", layout="centered", initial_sidebar_state="collapsed")

# =============================================================================
# 1. DESIGN (mêmes jetons que l'app Budget)
# =============================================================================
TOKENS = {
    "bg": "#030712", "bg-glow": "#172554",
    "text": "#F8FAFC", "text-muted": "#94A3B8", "text-dim": "#64748B",
    "blue-900": "#1E3A8A", "blue-600": "#2563EB", "blue-500": "#3B82F6", "blue-400": "#60A5FA", "blue-300": "#93C5FD",
    "green": "#34D399", "amber": "#FBBF24", "red": "#FB7185",
    "radius-lg": "24px", "radius-md": "16px", "radius-sm": "12px",
    "font": "'Lato', sans-serif",
    "grad-blue": "linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%)",
    "grad-blue-hover": "linear-gradient(90deg, #2A4CAE 0%, #3B82F6 100%)",
    "grad-blue-glass": "linear-gradient(90deg, rgba(30, 58, 138, 0.62) 0%, rgba(37, 99, 235, 0.62) 100%)",
    "glow-blue": "0 6px 15px rgba(37, 99, 235, 0.2), inset 0 1px 2px rgba(255,255,255,0.2)",
    "glow-blue-hover": "0 10px 30px rgba(59, 130, 246, 0.40), inset 0 1px 1px rgba(255, 255, 255, 0.40)",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap');
@import url('https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css');
.stApp { background-color: var(--bg); background-image: radial-gradient(circle at 50% -20%, var(--bg-glow) 0%, var(--bg) 85%); color: var(--text); font-family: var(--font); }
h1, h2, h3, h4 { color: #FFFFFF !important; font-weight: 700 !important; letter-spacing: -0.5px; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; }

/* boutons principaux */
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {
  background: var(--grad-blue) !important; border: 1px solid rgba(59,130,246,0.5) !important; border-radius: var(--radius-md) !important;
  box-shadow: var(--glow-blue) !important; color: #FFFFFF !important; font-weight: 900 !important; text-transform: uppercase !important; letter-spacing: 1.5px !important; }
[data-testid="stFormSubmitButton"] button { height: 3.6rem !important; width: 100%; }
[data-testid="stButton"] button { min-height: 2.6rem; width: 100%; }
[data-testid="stButton"] button p, [data-testid="stFormSubmitButton"] button p { color: #FFFFFF !important; font-weight: 900 !important; }
[data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover { background: var(--grad-blue-hover) !important; border-color: rgba(147,197,253,0.6) !important; box-shadow: var(--glow-blue-hover) !important; }
/* petits boutons d'action (relances) : verre */
[class*="st-key-act_"] button { background: rgba(15,23,42,0.6) !important; box-shadow: none !important; border: 1px solid rgba(59,130,246,0.35) !important; font-size: 12px !important; letter-spacing: 1px !important; }
[class*="st-key-act_"] button p { font-size: 12px !important; }

/* champs */
[data-testid="stTextInput"] [data-baseweb="input"], [data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"], [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  background-color: rgba(15,23,42,0.6) !important; border: 1px solid rgba(59,130,246,0.2) !important; border-radius: var(--radius-sm) !important; }
[data-testid="stTextInput"] input, [data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea { color: #FFFFFF !important; font-size: 16px !important; }
/* bloc « Raconte ta rencontre » */
[class*="st-key-dictee"] { background: linear-gradient(160deg, rgba(255,255,255,0.11) 0%, rgba(147,197,253,0.06) 55%, rgba(255,255,255,0.04) 100%);
  border: 1px solid rgba(255,255,255,0.20); border-radius: 24px; padding: 20px 18px 16px; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 12px 40px rgba(37,99,235,0.20), inset 0 1px 0 rgba(255,255,255,0.18); margin-bottom: 18px; }
[class*="st-key-dictee"] [data-testid="stTextArea"] [data-baseweb="textarea"] { background: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.22) !important; border-radius: 16px !important; }
[class*="st-key-dictee"] textarea::placeholder { color: rgba(226,232,240,0.55) !important; }
[class*="st-key-dictee"] [data-testid="stAudioInput"] > div, [class*="st-key-dictee"] [data-testid="stAudioInput"] section { background: rgba(255,255,255,0.10) !important;
  border: 1px solid rgba(255,255,255,0.28) !important; border-radius: 18px !important; }
/* validation des nouvelles : un bloc par personne */
[class*="st-key-nwcard"] { background: linear-gradient(160deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.015) 100%); border: 1px solid rgba(255,255,255,0.12);
  border-radius: 20px; padding: 18px 20px 8px; margin-top: 14px; box-shadow: 0 10px 28px rgba(0,0,0,0.28); }
[class*="st-key-nwcard"] [data-testid="stCheckbox"] label p { font-size: 11px !important; font-weight: 800 !important; letter-spacing: 0.7px; text-transform: uppercase; color: var(--text-muted) !important; }
[class*="st-key-nwcard"] [data-testid="stCheckbox"] { margin-top: 6px; }
[class*="st-key-nwcard"] [data-baseweb="textarea"], [class*="st-key-nwcard"] [data-baseweb="input"] { background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.14) !important; border-radius: 12px !important; }
[class*="st-key-nwcard"] textarea:disabled, [class*="st-key-nwcard"] input:disabled { opacity: 0.35; }
[class*="st-key-nwcard"] [data-testid="stExpander"] { background: transparent !important; border: 1px dashed rgba(255,255,255,0.14) !important; margin-top: 8px; }
[class*="st-key-nwcard"] [data-testid="stExpander"] summary p { font-size: 12.5px; color: var(--text-dim); }
.nw-val { display: flex; gap: 10px; margin: -2px 0 10px 32px; color: #E2E8F0; font-size: 14.5px; line-height: 1.55; overflow-wrap: anywhere; }
.nw-val i { color: var(--blue-400); font-size: 16px; margin-top: 3px; flex-shrink: 0; }
.nw-note { margin: -8px 0 12px 4px; color: var(--text-dim); font-size: 12px; font-weight: 600; }
/* rond du micro = logo Nexus */
[class*="st-key-dictee"] [data-testid="stAudioInput"] button[aria-label*="ecord" i]:not([aria-label*="top" i]),
[class*="st-key-dictee"] [data-testid="stAudioInput"] button[aria-label*="nregistr" i]:not([aria-label*="top" i]):not([aria-label*="rr" i]) {
  background: url("__NEXUS__") center/cover no-repeat !important; border-radius: 50% !important; border: 1px solid rgba(255,255,255,0.35) !important;
  box-shadow: 0 4px 16px rgba(109,40,217,0.45) !important; width: 40px !important; height: 40px !important; min-width: 40px !important; }
[class*="st-key-dictee"] [data-testid="stAudioInput"] button[aria-label*="ecord" i]:not([aria-label*="top" i]) svg,
[class*="st-key-dictee"] [data-testid="stAudioInput"] button[aria-label*="nregistr" i]:not([aria-label*="top" i]):not([aria-label*="rr" i]) svg { opacity: 0 !important; }
.dict-title { display: flex; align-items: center; gap: 10px; color: #FFFFFF; font-size: 20px; font-weight: 900; letter-spacing: 0.3px; }
.dict-title i { font-size: 24px; color: var(--blue-300); }
.dict-sub { color: #CBD5E1; font-size: 13.5px; line-height: 1.5; margin: 6px 0 12px; }
.check-title { color: #FFFFFF; font-size: 16px; font-weight: 900; letter-spacing: 1px; text-transform: uppercase; margin: 4px 0 8px; }
.check-title span { color: var(--amber); font-size: 12px; letter-spacing: 0.5px; text-transform: none; margin-left: 8px; }
label, [data-testid="stWidgetLabel"] p { color: var(--text-muted) !important; font-size: 12px !important; font-weight: 700 !important; letter-spacing: 1px; text-transform: uppercase; }
[data-baseweb="popover"] ul, [role="listbox"] { background: rgba(15,23,42,0.95) !important; border: 1px solid rgba(147,197,253,0.3) !important; border-radius: 14px !important; }
[role="option"] { color: #FFFFFF !important; }

/* pastilles (catégorie, relation) */
[data-testid="stPills"] button, [data-testid="stButtonGroup"] button {
  border-radius: 999px !important; border: 1px solid rgba(59,130,246,0.25) !important; background: rgba(15,23,42,0.6) !important; color: var(--text-muted) !important; font-weight: 700 !important; }
[data-testid="stPills"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stPills"] button[kind*="Active"], [data-testid="stButtonGroup"] button[kind*="Active"] {
  background: var(--grad-blue) !important; color: #FFFFFF !important; border-color: rgba(59,130,246,0.6) !important; }

/* onglets */
[role="tablist"] { gap: 8px; background-color: rgba(15,23,42,0.7); padding: 8px 12px; border-radius: 26px; border: 1px solid rgba(59,130,246,0.2); backdrop-filter: blur(25px); margin-bottom: 28px; justify-content: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
[role="tablist"] > div[aria-hidden="true"], [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none !important; }
[role="tab"] { height: 50px; background-color: transparent !important; border-radius: var(--radius-md) !important; padding: 0 22px !important; }
[role="tab"] p { color: var(--text-dim) !important; font-weight: 700 !important; font-size: 14px !important; text-transform: uppercase; letter-spacing: 1.2px; }
[role="tab"][aria-selected="true"] { background-color: rgba(37,99,235,0.15) !important; }
[role="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-weight: 900 !important; text-shadow: 0 0 15px rgba(255,255,255,0.4); }

/* expanders : verre (liste de contacts, options) */
[data-testid="stExpander"] { background: rgba(15,23,42,0.25) !important; border: 1px solid rgba(59,130,246,0.25) !important; border-radius: var(--radius-md) !important; margin-bottom: 10px !important; overflow: hidden; }
[data-testid="stExpander"] summary { padding: 12px 16px !important; }
[data-testid="stExpander"] summary:hover { background: rgba(59,130,246,0.10) !important; }
[data-testid="stExpander"] summary p { color: #FFFFFF !important; font-weight: 700 !important; letter-spacing: 0.3px; }
[data-testid="stForm"] { border: 1px solid rgba(59,130,246,0.2) !important; border-radius: var(--radius-lg) !important; background: rgba(15,23,42,0.3); padding: 18px !important; }

/* en-tête */
.page-title { color: #FFFFFF; font-size: 40px; font-weight: 900; letter-spacing: -1px; line-height: 1.1; }
.page-sub { color: var(--text-muted); font-size: 16px; margin-top: 6px; }
.page-sub b { color: var(--blue-400); }
.section-title { color: #FFFFFF; font-weight: 800; font-size: 15px; letter-spacing: 1.5px; text-transform: uppercase; margin: 22px 0 10px; display: flex; align-items: center; gap: 8px; }
.section-title .count { color: var(--blue-300); background: rgba(37,99,235,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 999px; padding: 1px 10px; font-size: 12px; }
.hint { color: var(--text-dim); font-size: 14px; text-align: center; padding: 18px; border: 1px dashed rgba(59,130,246,0.25); border-radius: var(--radius-md); }

/* KPI */
.nw-grid { display: flex; gap: 10px; margin: 18px 0 6px; }
.nw-card { flex: 1; background: rgba(15,23,42,0.5); border: 1px solid rgba(59,130,246,0.2); border-radius: var(--radius-md); padding: 12px 8px; text-align: center; }
.nw-title { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 4px; }
.nw-value { font-size: 22px; font-weight: 900; }

/* carte contact */
.card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 18px; margin-bottom: 12px; }
.nc { padding: 18px 20px; }
.nc-head { display: flex; align-items: center; gap: 14px; }
.nc-photo { padding: 0; overflow: hidden; }
.nc-photo img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; display: block; }
.nc-avatar { width: 46px; height: 46px; border-radius: 50%; flex-shrink: 0; display: grid; place-items: center; font-weight: 900; font-size: 16px; color: var(--blue-300);
  background: radial-gradient(circle at 30% 30%, rgba(59,130,246,0.35), rgba(15,23,42,0.9)); border: 2px solid rgba(96,165,250,0.4); box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
.nc-id { flex: 1; min-width: 0; }
.nc-name { color: #FFFFFF; font-size: 17px; font-weight: 700; }
.nc-name b { font-weight: 900; letter-spacing: 0.3px; }
.nc-sub { color: var(--text-muted); font-size: 13px; margin-top: 2px; font-weight: 600; }
.nc-li { color: var(--blue-400) !important; font-size: 24px; text-decoration: none; }
.nc-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; color: var(--blue-300); background: rgba(37,99,235,0.12); border: 1px solid rgba(59,130,246,0.28); }
.chip--hot { color: var(--red); background: rgba(225,29,72,0.12); border-color: rgba(225,29,72,0.3); }
.chip--warm { color: var(--amber); background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.3); }
.chip--cold { color: #7DD3FC; background: rgba(56,189,248,0.10); border-color: rgba(56,189,248,0.28); }
.chip--assoc { color: var(--green); background: rgba(52,211,153,0.10); border-color: rgba(52,211,153,0.28); }
.nc-fold > summary { list-style: none; cursor: pointer; }
.nc-fold > summary::-webkit-details-marker { display: none; }
.nc-toggle { margin-top: 10px; font-size: 12px; font-weight: 700; color: var(--blue-300); }
.nc-toggle::after { content: "Voir la fiche ▾"; }
.nc-fold[open] .nc-toggle::after { content: "Masquer ▴"; }
.nc-note { margin-top: 10px; font-size: 13px; color: var(--text-muted); font-weight: 600; }
.ev-line { padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 14px; color: #E2E8F0; }
.ev-line b { color: #FFFFFF; }
.ev-line span { color: var(--text-muted); font-size: 13px; }
.nc-task { margin-top: 12px; padding: 9px 12px; border-radius: 12px; font-size: 13px; font-weight: 700; color: var(--amber); background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.25); }
.nc-task.late { color: var(--red); background: rgba(225,29,72,0.10); border-color: rgba(225,29,72,0.3); }
.nc-rows { display: grid; grid-template-columns: 128px minmax(0, 1fr); gap: 14px 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.07); }
.nc-k { display: flex; gap: 7px; align-items: flex-start; font-size: 11px; font-weight: 800; letter-spacing: 0.7px; text-transform: uppercase; color: var(--text-dim); padding-top: 3px; }
.nc-k i { color: var(--blue-400); font-size: 15px; margin-top: -1px; }
.nc-v { color: #E2E8F0; font-size: 14px; line-height: 1.55; min-width: 0; overflow-wrap: anywhere; }
.nc-v ul { margin: 0; padding-left: 18px; }
.nc-v li { margin: 0 0 5px; }
.nc-v li:last-child { margin-bottom: 0; }
.nc-v.quote { font-style: italic; color: #CBD5E1; }
.nc-v.small { font-size: 13px; color: #CBD5E1; }
.nc-more { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.nc-empty { color: var(--text-dim); font-style: italic; font-size: 13px; }
.nc-foot { margin-top: 16px; color: var(--text-dim); font-size: 12px; }

@media (max-width: 768px) {
  .page-title { font-size: 32px; }
  [role="tablist"] { gap: 4px; padding: 5px 6px; }
  [role="tab"] { padding: 0 10px !important; }
  [role="tab"] p { font-size: 12px !important; }
  [data-testid="stForm"] { padding: 12px !important; }
  .nc { padding: 16px 14px; }
  .nc-rows { grid-template-columns: 1fr; gap: 3px; }
  .nc-k { margin-top: 10px; }
  .nc-k:first-child { margin-top: 0; }
}
"""


NEXUS_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
             "<stop offset='0' stop-color='#0f172a'/><stop offset='1' stop-color='#6d28d9'/></linearGradient></defs>"
             "<rect width='64' height='64' rx='16' fill='url(#g)'/><path d='M18 46V18h6l16 20V18h6v28h-6L24 26v20z' fill='#fff'/>"
             "<circle cx='50' cy='14' r='5.5' fill='#10b981'/></svg>")


def inject_css():
    from urllib.parse import quote
    root = ":root{" + "".join(f"--{k}:{v};" for k, v in TOKENS.items()) + "}"
    css = CSS.replace("__NEXUS__", "data:image/svg+xml," + quote(NEXUS_SVG, safe="/:=' "))
    st.markdown(f"<style>{root}{css}</style>", unsafe_allow_html=True)


inject_css()

# =============================================================================
# 2. ACCÈS
# =============================================================================
def secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


PASSWORD = secret("app_password")
if PASSWORD and not st.session_state.get("auth"):
    st.markdown("<div class='page-title'>Network</div><div class='page-sub'>Accès privé</div>", unsafe_allow_html=True)
    with st.form("login"):
        pw = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer"):
            if pw == PASSWORD:
                st.session_state.auth = True
                st.rerun()
            st.error("Mot de passe incorrect.")
    st.stop()


# =============================================================================
# 3. DONNÉES
# =============================================================================
@st.cache_resource(show_spinner=False)
def get_store():
    sa = secret("gcp_service_account")
    if not sa:
        return nc.CsvStore(Path(__file__).with_name("network_local.csv")), "local"
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_info(dict(sa), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    sheet_id = secret("network_sheet_id")
    if not sheet_id:
        raise RuntimeError("Ajoute network_sheet_id dans les secrets (identifiant du Google Sheet).")
    return nc.SheetStore(gspread.authorize(creds), sheet_id), "gsheet"


try:
    store, MODE = get_store()
except Exception as ex:
    st.error(f"Connexion au Google Sheet impossible : {ex}")
    st.info("Vérifie que le Google Sheet est partagé (éditeur) avec l'adresse e-mail du compte de service, et que network_sheet_id est juste.")
    st.stop()

st.session_state.setdefault("ver", 0)


@st.cache_data(ttl=60, show_spinner=False)
def load(ver):
    return store.all()


@st.cache_data(ttl=300, show_spinner=False)
def load_photos(ver):
    try:
        return store.photos()
    except Exception:
        return {}


def refresh():
    st.session_state.ver += 1


def save_update(cid, changes, msg="Enregistré"):
    try:
        store.update(cid, changes)
        refresh()
        st.toast(msg, icon="✅")
    except Exception as ex:
        st.error(f"Échec de l'enregistrement : {ex}")


contacts = load(st.session_state.ver)
photos = load_photos(st.session_state.ver) if hasattr(store, "photos") else {}
today = date.today()
late, week, later = nc.relances(contacts, today)

# =============================================================================
# 4. EN-TÊTE
# =============================================================================
n_month = sum(1 for c in contacts if (nc.parse_date(c["date_rencontre"]) or nc.parse_date(c["cree_le"][:10]) or date.min) >= today - timedelta(days=30))
st.markdown("".join([
    "<div class='page-title'>Network</div>",
    f"<div class='page-sub'><b>{len(contacts)}</b> contacts · <b>{n_month}</b> ce mois-ci</div>",
    "" if MODE == "gsheet" else "<div class='page-sub' style='color:var(--amber);font-size:13px;'>Mode local (CSV) : aucun Google Sheet configuré.</div>",
    nc.kpi_html([("En retard", len(late), "var(--red)"), ("Cette semaine", len(week), "var(--amber)")]),
]), unsafe_allow_html=True)

tab_add, tab_news, tab_net, tab_ev, tab_rel = st.tabs(["Ajouter", "Nouvelles", "Réseau", "Événement", "À relancer"])

CAT_NAMES = [c for c, _ in nc.CATEGORIES]
ECOLES = sorted({c.get("ecole", "") for c in contacts if c.get("ecole")}, key=nc.norm)
EMPLOYEURS = sorted({c.get("employeur", "") for c in contacts if c.get("employeur")}, key=nc.norm)
FONCTIONS = sorted({c.get("fonction", "") for c in contacts if c.get("fonction")}, key=nc.norm)


def combo(label, options, value="", key=None, placeholder=""):
    """Liste qui propose les valeurs déjà saisies, mais accepte n'importe quelle nouvelle valeur (tape-la puis Entrée)."""
    opts = list(options)
    if value and value not in opts:
        opts = [value] + opts
    try:
        v = st.selectbox(label, opts, index=opts.index(value) if value in opts else None, key=key,
                         accept_new_options=True, placeholder=placeholder or "Choisis ou tape…")
        return (v or "").strip()
    except TypeError:                                   # Streamlit trop ancien : simple champ texte
        return st.text_input(label, value, key=key, placeholder=placeholder).strip()


def pick(label, options, value="", key=None):
    opts = ["—"] + options
    v = st.selectbox(label, opts, index=opts.index(value) if value in opts else 0, key=key)
    return "" if v == "—" else v


ASSOC_OPTS = nc.all_associations(contacts)


def assoc_field(c=None, k="add"):
    """Associations : plusieurs choix, liste proposée + nouvelles valeurs acceptées."""
    cur = nc.assoc_list(c or {})
    opts = ASSOC_OPTS + [a for a in cur if a not in ASSOC_OPTS]
    try:
        v = st.multiselect("Associations", opts, default=cur, key=f"{k}_assoc", accept_new_options=True,
                           placeholder="GUIC, Comité GSEM, IFSA…")
    except TypeError:
        v = st.multiselect("Associations", opts, default=cur, key=f"{k}_assoc")
    return ", ".join(x.strip() for x in v if x.strip())


def study_job_fields(c=None, k="add"):
    c = c or {}
    c1, c2, c3 = st.columns([3, 1.4, 1.8])
    with c1:
        ecole = combo("École / faculté", ECOLES, c.get("ecole", ""), key=f"{k}_ecole", placeholder="GSEM, HEC Lausanne…")
    with c2:
        niveau = pick("Niveau", nc.NIVEAUX, c.get("niveau", ""), key=f"{k}_niv")
    with c3:
        etudes = pick("Études", nc.ETUDES, c.get("etudes", ""), key=f"{k}_etu")
    c1, c2 = st.columns(2)
    with c1:
        employeur = combo("Employeur", EMPLOYEURS, c.get("employeur", ""), key=f"{k}_emp", placeholder="UBS, Pictet, EY…")
    with c2:
        fonction = combo("Poste", FONCTIONS, c.get("fonction", ""), key=f"{k}_fon", placeholder="Analyst, stage, temps partiel…")
    return dict(ecole=ecole, niveau=niveau, etudes=etudes, employeur=employeur, fonction=fonction)


def choice(label, options, key, default=None):
    """Pastilles si la version de Streamlit les a, sinon liste déroulante."""
    if hasattr(st, "pills"):
        return st.pills(label, options, key=key, default=default)
    idx = options.index(default) + 1 if default in options else 0
    v = st.selectbox(label, ["—"] + options, index=idx, key=key)
    return None if v == "—" else v


# =============================================================================
# 5. AJOUTER
# =============================================================================
GEMINI_KEY = secret("GEMINI_API_KEY") or secret("gemini_api_key")

with tab_add:
    rnd_a = st.session_state.setdefault("add_round", 0)
    pf = st.session_state.setdefault("add_pref", {})
    k = f"a{rnd_a}"
    try:
        hero = st.container(key="dictee")
    except TypeError:
        hero = st.container(border=True)
    with hero:
        st.markdown("<div class='dict-title'><i class='ph ph-microphone'></i>Raconte ta rencontre</div>", unsafe_allow_html=True)
        audio = None
        if GEMINI_KEY and hasattr(st, "audio_input"):
            audio = st.audio_input("Dicter", key=f"{k}_mic", label_visibility="collapsed")
        desc = st.text_area("Description libre", pf.get("_desc", ""), height=120, key=f"{k}_desc", label_visibility="collapsed",
                            placeholder="… ou écris ici. Ex. : Philippe Bulgaris, rencontré à la soirée GUIC, en master à HEC Lausanne, "
                                        "très calme, fait du trail, veut bosser en private markets. M'a conseillé de… On se revoit mi-novembre.")
        prefill = st.button("Pré-remplir avec l'IA", key=f"{k}_aibtn", disabled=not GEMINI_KEY, use_container_width=True)
        li_file = None
        if GEMINI_KEY:
            li_file = st.file_uploader("Ou importe son profil LinkedIn (PDF « Enregistrer au format PDF », ou .md / .txt)",
                                       type=["pdf", "md", "txt"], key=f"{k}_liup")
        if not GEMINI_KEY:
            st.caption("Ajoute GEMINI_API_KEY dans les Secrets pour activer la dictée et le pré-remplissage.")
    filled = pf.get("_ai")
    st.markdown("<div class='check-title'>Vérifie et complète" + ("<span>pré-rempli par l'IA</span>" if filled else "") + "</div>",
                unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        prenom = c1.text_input("Prénom *", pf.get("prenom", ""), placeholder="Prénom", key=f"{k}_pre")
        nom = c2.text_input("Nom *", pf.get("nom", ""), placeholder="Nom", key=f"{k}_nom")
        cat = choice("Catégorie", CAT_NAMES, key=f"{k}_cat", default=pf.get("categorie") or None)
        sj = study_job_fields(pf, k)
        sj["associations"] = assoc_field(pf, k)
        c1, c2 = st.columns([3, 2])
        ou = c1.text_input("Rencontré où", pf.get("rencontre_ou", ""), placeholder="Wick, soirée GUIC, cours…", key=f"{k}_ou")
        quand = c2.date_input("Quand", value=nc.parse_date(pf.get("date_rencontre")) or today, format="DD.MM.YYYY", key=f"{k}_quand")
        raconte = st.text_area("Personnalité, relation", pf.get("raconte", ""), placeholder="Comment il fonctionne, son caractère, comment vous vous entendez, son parcours…", height=90, key=f"{k}_rac")
        projets = st.text_area("Projets d'avenir", pf.get("projets", ""), placeholder="Master visé, poste rêvé, création de boîte, départ à l'étranger…", height=80, key=f"{k}_proj")
        c1, c2 = st.columns(2)
        hobbies = c1.text_input("Hobbies, sport", pf.get("hobbies", ""), placeholder="Trail, ski, échecs…", key=f"{k}_hob")
        communs = c2.text_input("Points communs", pf.get("points_communs", ""), placeholder="Même école, même club…", key=f"{k}_com")
        conseil = st.text_area("Conseil qu'il m'a donné (ou citation)", pf.get("conseil", ""), placeholder="Un conseil sur le métier, la carrière, la vie… ou une phrase à retenir", height=80, key=f"{k}_cons")
        anecdote = st.text_area("Anecdote / phrase marquante", pf.get("anecdote", ""), placeholder="La phrase drôle, le détail niche qu'il t'a raconté…", height=80, key=f"{k}_anec")
        utile = st.text_input("Valeur ajoutée dans mon réseau", pf.get("utile_pour", ""), placeholder="Regard d'expert sur le PE, porte d'entrée chez Pictet, bon conseil carrière…", key=f"{k}_util")
        relation = choice("Relation", nc.RELATIONS, key=f"{k}_rel", default=pf.get("relation") or "Network")
        with st.expander("Suivi et coordonnées", expanded=bool(pf.get("tache"))):
            tache = st.text_input("Tâche à faire", pf.get("tache", ""), placeholder="Lui écrire sur LinkedIn, envoyer le CV…", key=f"{k}_tache")
            c1, c2 = st.columns(2)
            ech = c1.date_input("Échéance", value=nc.parse_date(pf.get("echeance")), format="DD.MM.YYYY", key=f"{k}_ech")
            tel = c2.text_input("Numéro", pf.get("telephone", ""), placeholder="+41 …", key=f"{k}_tel")
            li = st.text_input("Lien LinkedIn", pf.get("linkedin", ""), placeholder="https://www.linkedin.com/in/…", key=f"{k}_li")
        ok = st.button("Enregistrer", type="primary", key=f"{k}_save")
    current = dict(prenom=prenom, nom=nom, categorie=cat or "", **sj, rencontre_ou=ou, date_rencontre=nc.iso(quand), raconte=raconte,
                   projets=projets, hobbies=hobbies, points_communs=communs, conseil=conseil, anecdote=anecdote, utile_pour=utile,
                   relation=relation or "", tache=tache, echeance=nc.iso(ech), telephone=tel, linkedin=li, _desc=desc)
    direct_a = None
    if audio is not None:
        import hashlib
        h = hashlib.md5(audio.getvalue()).hexdigest()
        # « fait » seulement après une transcription réussie ; après un échec, on ne réessaie qu'au clic sur le bouton
        if h != st.session_state.get("mic_done") and (h != st.session_state.get("mic_fail") or prefill):
            heard, err = None, None
            import time as _t
            _t0 = _t.time()
            if secret("dictee_directe") == "oui":                    # voie rapide : un seul appel, le modèle écoute et remplit
                with st.spinner("J'écoute et j'analyse ta dictée…"):
                    try:
                        known0 = {f: v for f, v in current.items() if f in ("prenom", "nom", "categorie", "ecole", "employeur") and v}
                        if st.session_state.get("add_pref", {}).get("_ai"):
                            known0 = {}
                        r0, m0 = nc.gemini_audio_json(nc.contact_prompt(desc.strip() or "(voir l'enregistrement audio)", today.isoformat(), known0),
                                                      audio.getvalue(), getattr(audio, "type", None) or "audio/wav", GEMINI_KEY, secret("gemini_model") or None, transcript=secret("dictee_texte") == "oui")
                        h0 = str(r0.get("transcription") or "").strip()
                        if h0 or r0.get("champs"):
                            direct_a, heard = r0, h0
                    except Exception:
                        direct_a = None                              # repli : transcription puis analyse
            if direct_a is None:
                with st.spinner("Transcription de ta dictée…"):
                    try:
                        heard = nc.transcribe(audio.getvalue(), getattr(audio, "type", None) or "audio/wav", GEMINI_KEY, secret("gemini_model_dictee") or None)
                    except Exception as ex:
                        err = f"{type(ex).__name__} : {ex}"
            st.session_state.t_dictee = None if direct_a else _t.time() - _t0
            st.session_state.t_direct = _t.time() - _t0 if direct_a else None
            if heard or direct_a:
                st.session_state.mic_done = h
                desc = (desc.strip() + " " + (heard or "")).strip()
                current["_desc"] = desc
                prefill = True                                   # dictée -> pré-remplissage directement
            else:
                st.session_state.mic_fail = h
                st.error("Dictée non transcrite : " + (err or "aucun texte entendu (parle plus longtemps ou plus près du micro)")
                         + ". Appuie sur « Pré-remplir avec l'IA » pour réessayer.")
    if li_file is not None:
        import hashlib
        import time as _tl
        lh = hashlib.md5(li_file.getvalue()).hexdigest()
        if lh != st.session_state.get("li_done") and (lh != st.session_state.get("li_fail") or prefill):
            _t0 = _tl.time()
            with st.spinner("Lecture du profil LinkedIn…"):
                try:
                    raw = li_file.getvalue()
                    txt_li = nc.profile_text(raw, li_file.name)
                    if len(txt_li) >= 80:
                        res_li, m_li = nc.gemini_json(nc.linkedin_prompt(txt_li, today.isoformat()), GEMINI_KEY, secret("gemini_model") or None, think="low")
                    elif li_file.name.lower().endswith(".pdf"):
                        res_li, m_li = nc.gemini_pdf_json(nc.linkedin_prompt("(voir le PDF joint)", today.isoformat()), raw, GEMINI_KEY,
                                                         secret("gemini_model") or None)
                    else:
                        raise RuntimeError("fichier vide ou illisible")
                    ch = dict((res_li or {}).get("champs") or {})
                    ch.setdefault("rencontre_ou", "LinkedIn")
                    ch.setdefault("relation", "À contacter")
                    direct_a, prefill = {"champs": ch}, True
                    st.session_state.li_done = lh
                    st.session_state.t_dictee, st.session_state.t_direct = None, None
                    st.session_state.from_li = f"profil LinkedIn lu en {_tl.time() - _t0:.0f} s · {m_li}"
                except Exception as ex:
                    st.session_state.li_fail = lh
                    st.error(f"Profil non lu : {ex}. Appuie sur « Pré-remplir avec l'IA » pour réessayer.")
    if prefill:
        done_ai = False
        if not desc.strip() and not direct_a:
            st.warning("Écris ou dicte d'abord quelques phrases dans la description.")
        else:
            import time as _t2
            _t1 = _t2.time()
            with st.spinner("Analyse en cours…"):
                try:
                    known = {f: v for f, v in current.items() if f in ("prenom", "nom", "categorie", "ecole", "employeur") and v}
                    if st.session_state.get("add_pref", {}).get("_ai"):
                        known = {}                               # nouvelle analyse : l'IA peut tout reproposer
                    _m = "audio direct"
                    if direct_a:
                        res = direct_a
                    else:
                        res, _m = nc.gemini_json(nc.contact_prompt(desc, today.isoformat(), known), GEMINI_KEY, secret("gemini_model") or None)
                    ai = nc.clean_contact_fields(res)
                    merged = dict(current)
                    for f, v in ai.items():
                        if f == "relation" and current.get("relation") in ("", "Network"):
                            merged[f] = v
                        elif not str(current.get(f) or "").strip():
                            merged[f] = v                        # l'IA remplit seulement les cases vides
                    merged["_ai"] = True
                    st.session_state.add_pref = merged
                    st.session_state.add_round = rnd_a + 1
                    _td = st.session_state.pop("t_dictee", None)
                    _tdir = st.session_state.pop("t_direct", None)
                    _fli = st.session_state.pop("from_li", None)
                    st.session_state.add_msg = (f"{len(ai)} champ(s) pré-rempli(s) : vérifie, corrige, puis Enregistrer. "
                                                + (f"({_fli})" if _fli else f"(écoute + analyse en un appel : {_tdir:.0f} s)" if _tdir else
                                                   f"({'dictée ' + format(_td, '.0f') + ' s, ' if _td else ''}analyse {_t2.time() - _t1:.0f} s · {_m})"))
                    done_ai = True
                except Exception as ex:
                    st.error(f"Analyse impossible : {ex}. Ta description reste dans la case.")
        if done_ai:
            st.rerun()
    msg = st.session_state.pop("add_msg", None)
    if msg:
        st.info(msg)
    if ok:
        if not prenom.strip() or not nom.strip():
            st.error("Il faut au moins le prénom et le nom.")
        else:
            dup = nc.duplicates(contacts, prenom, nom)
            fields = {f: v for f, v in current.items() if not f.startswith("_")}
            fields["dernier_contact"] = fields["date_rencontre"]
            c = nc.new_contact(**fields)
            saved = False
            try:
                store.add(c)
                refresh()
                st.session_state.add_pref = {}
                st.session_state.add_round = rnd_a + 1
                st.toast(f"{c['prenom']} {c['nom'].upper()} ajouté(e)", icon="✅")
                if dup:
                    st.session_state.add_msg = f"Il y avait déjà un(e) {c['prenom']} {c['nom'].upper()} dans ton réseau : vérifie le doublon dans l'onglet Réseau."
                saved = True
            except Exception as ex:
                st.error(f"Échec de l'enregistrement : {ex}")
            if saved:
                st.rerun()


# =============================================================================
# 5 bis. NOUVELLES (texte libre rangé par Gemini, validé avant enregistrement)
# =============================================================================
GEMINI_KEY = secret("GEMINI_API_KEY") or secret("gemini_api_key")
NEW, SKIP = "__new__", "__skip__"
NEWS_ORDER = ["ecole", "niveau", "etudes", "employeur", "fonction", "associations", "categorie", "relation", "raconte", "projets", "hobbies",
              "points_communs", "conseil", "anecdote", "utile_pour", "tache", "echeance"]
NEWS_ICON = {"ecole": "ph-graduation-cap", "niveau": "ph-student", "etudes": "ph-books", "employeur": "ph-buildings", "fonction": "ph-briefcase",
             "associations": "ph-users-three", "categorie": "ph-tag", "relation": "ph-tag", "raconte": "ph-user-focus", "projets": "ph-rocket-launch",
             "hobbies": "ph-person-simple-run", "points_communs": "ph-link-simple", "conseil": "ph-lightbulb", "anecdote": "ph-sparkle",
             "utile_pour": "ph-star", "tache": "ph-check-square", "echeance": "ph-calendar-blank", "historique": "ph-clock-counter-clockwise"}
by_id = {c["id"]: c for c in contacts}


def contact_label(x):
    if x == NEW:
        return "➕ Nouveau contact"
    if x == SKIP:
        return "Ignorer cette personne"
    c = by_id.get(x, {})
    return f"{c.get('prenom', '')} {c.get('nom', '').upper()}" + (f" · {c['institution']}" if c.get("institution") else "")


with tab_news:
    if not GEMINI_KEY:
        st.warning("Ajoute GEMINI_API_KEY dans les Secrets de l'app (Streamlit Cloud → Settings → Secrets) pour activer l'analyse.")
    rnd = st.session_state.setdefault("news_round", 0)
    ver = st.session_state.setdefault("news_ver", 0)
    people_ids = [c["id"] for c in sorted(contacts, key=lambda c: (nc.norm(c["prenom"]), nc.norm(c["nom"])))]
    try:
        hero_n = st.container(key="dictee_news")
    except TypeError:
        hero_n = st.container(border=True)
    with hero_n:
        st.markdown("<div class='dict-title'><i class='ph ph-microphone'></i>Raconte ta soirée ou ta rencontre</div>", unsafe_allow_html=True)
        naudio = None
        if GEMINI_KEY and hasattr(st, "audio_input"):
            naudio = st.audio_input("Dicter", key=f"news_mic_{rnd}", label_visibility="collapsed")
        txt = st.text_area("Récit", st.session_state.get("news_txt", ""), height=140, key=f"news_txt_{rnd}_{ver}", label_visibility="collapsed",
                           placeholder="… ou écris ici. Ex. : Soirée alumni GUIC. Kylian : passé chez Cabelo, conseille de postuler aux stages dès janvier, "
                                       "café mi-novembre. Sarah : en M1 à HEC, veut faire du private equity, je dois lui envoyer mon CV.")
        with st.expander("Préciser les personnes ou la date (facultatif)"):
            c1, c2 = st.columns([3, 2])
            picked = c1.multiselect("Personnes", people_ids, format_func=contact_label, placeholder="Tape « dio », « pictet »…", key=f"news_pick_{rnd}")
            ev_date = c2.date_input("Date", value=today, format="DD.MM.YYYY", key=f"news_date_{rnd}")
        go = st.button("Analyser avec l'IA", key=f"news_go_{rnd}", disabled=not GEMINI_KEY, use_container_width=True)

    direct = None
    if naudio is not None:
        import hashlib
        import time as _tn
        nh = hashlib.md5(naudio.getvalue()).hexdigest()
        if nh != st.session_state.get("nmic_done") and (nh != st.session_state.get("nmic_fail") or go):
            heard, err = None, None
            _t0 = _tn.time()
            if secret("dictee_directe") == "oui":                    # voie rapide : un seul appel, le modèle écoute et range
                with st.spinner("J'écoute et j'analyse ta dictée…"):
                    try:
                        sel0 = [by_id[x] for x in picked if x in by_id]
                        r0, m0 = nc.gemini_audio_json(nc.news_prompt(txt.strip() or "(voir l'enregistrement audio)", contacts, today.isoformat(),
                                                                     ev_date.isoformat(), sel0),
                                                      naudio.getvalue(), getattr(naudio, "type", None) or "audio/wav", GEMINI_KEY, secret("gemini_model") or None, transcript=secret("dictee_texte") == "oui")
                        h0 = str(r0.get("transcription") or "").strip()
                        if h0 or r0.get("personnes"):
                            direct, heard = (r0, m0), h0
                    except Exception:
                        direct = None                                # repli : transcription puis analyse
            if direct is None:
                with st.spinner("Transcription de ta dictée…"):
                    try:
                        heard = nc.transcribe(naudio.getvalue(), getattr(naudio, "type", None) or "audio/wav", GEMINI_KEY, secret("gemini_model_dictee") or None)
                    except Exception as ex:
                        err = f"{type(ex).__name__} : {ex}"
            st.session_state.t_dictee_n = None if direct else _tn.time() - _t0
            st.session_state.t_direct_n = _tn.time() - _t0 if direct else None
            if heard or direct:
                st.session_state.nmic_done = nh
                txt = (txt.strip() + " " + (heard or "")).strip()
                go = True                                            # dictée -> analyse directement
            else:
                st.session_state.nmic_fail = nh
                st.error("Dictée non transcrite : " + (err or "aucun texte entendu (parle plus longtemps ou plus près du micro)")
                         + ". Appuie sur « Analyser avec l'IA » pour réessayer.")
    analysed = False
    if go:
        if not txt.strip() and not direct:
            st.warning("Écris ou dicte d'abord ton récit.")
        else:
            import time as _tn2
            _t1 = _tn2.time()
            with st.spinner("Analyse en cours…"):
                try:
                    sel = [by_id[x] for x in picked if x in by_id]
                    if direct:
                        res, model = direct
                    else:
                        res, model = nc.gemini_json(nc.news_prompt(txt, contacts, today.isoformat(), ev_date.isoformat(), sel),
                                                    GEMINI_KEY, secret("gemini_model") or None, timeout=35, deadline=40.0)
                    props = nc.clean_proposal(res, contacts)
                    if len(sel) == 1 and len(props) == 1 and not props[0]["contact_id"]:
                        props[0]["contact_id"] = sel[0]["id"]          # une seule personne choisie : c'est elle
                    st.session_state.news = dict(props=props, date=ev_date.isoformat(), name=str((res or {}).get("evenement") or ""),
                                                 model=model, n=st.session_state.get("news_n", 0) + 1)
                    st.session_state.news_n = st.session_state.news["n"]
                    st.session_state.news_txt = txt
                    st.session_state.news_ver = ver + 1                # le récit (dicté) apparaît dans la zone de texte
                    _td = st.session_state.pop("t_dictee_n", None)
                    _tdir = st.session_state.pop("t_direct_n", None)
                    st.session_state.news_info = (f"{len(props)} personne(s) repérée(s) : vérifie ci-dessous. "
                                                  + (f"(écoute + analyse en un appel : {_tdir:.0f} s)" if _tdir else
                                                     f"({'dictée ' + format(_td, '.0f') + ' s, ' if _td else ''}analyse {_tn2.time() - _t1:.0f} s · {model})"))
                    analysed = True
                except Exception as ex:
                    st.error(f"Analyse impossible : {ex}. Ton texte reste dans la zone ci-dessus.")
    if analysed:
        st.rerun()
    info = st.session_state.pop("news_info", None)
    if info:
        st.info(info)

    news = st.session_state.get("news")
    if news:
        props, k0 = news["props"], f"nw{news['n']}"
        ev_name = st.text_input("Événement (deviné, modifiable)", news["name"], key=f"{k0}_ev", placeholder="Soirée alumni, coffee chat…")
        if not props:
            st.info("Aucune personne repérée dans le texte.")
        others = [c["id"] for c in sorted(contacts, key=lambda c: (nc.norm(c["prenom"]), nc.norm(c["nom"])))]
        plan = []
        for i, p in enumerate(props):
            first = ([p["contact_id"]] if p["contact_id"] else []) + [x for x in p["candidats"] if x != p["contact_id"]]
            opts = first + [NEW, SKIP] + [x for x in others if x not in first]
            default = first[0] if first else NEW
            try:
                card = st.container(key=f"nwcard_{news['n']}_{i}")
            except TypeError:
                card = st.container(border=True)
            with card:
                head = st.empty()
                if p["doute"]:
                    st.warning(p["doute"])
                rows_box = st.container()
                # le contact est déjà indiqué en haut : le changement (ou « ignorer ») reste discret, ouvert seulement en cas de doute
                with st.expander("Ce n'est pas la bonne personne ? Changer ou ignorer", expanded=bool(p["doute"] or len(first) > 1)):
                    target = st.selectbox("Contact", opts, index=opts.index(default), key=f"{k0}_t{i}", format_func=contact_label)
                    pr, no = p["prenom"], p["nom"]
                    if target == NEW:
                        c1, c2 = st.columns(2)
                        pr = c1.text_input("Prénom", p["prenom"], key=f"{k0}_p{i}")
                        no = c2.text_input("Nom", p["nom"], key=f"{k0}_n{i}")
            if target == SKIP:
                head.markdown("<div class='nc-sub'>Personne ignorée : rien ne sera enregistré.</div>", unsafe_allow_html=True)
                continue
            cur_c = by_id.get(target, {})
            fields, h, n_items = {}, "", 0
            order = [f for f in NEWS_ORDER if f in p["champs"]] + [f for f in p["champs"] if f not in NEWS_ORDER]
            h_default = nc.hist_line(news["date"], ev_name, p["historique"])
            with rows_box:
                for f in order + (["historique"] if h_default.strip() else []):
                    v = h_default if f == "historique" else p["champs"][f]
                    if not (v or "").strip() and f != "echeance":
                        continue
                    use = st.checkbox(nc.LABELS.get(f, f), value=True, key=f"{k0}_u{i}_{f}")
                    kk = f"{k0}_v{i}_{f}"
                    if f == "echeance":
                        val = nc.iso(st.date_input("Échéance", value=nc.parse_date(v), format="DD.MM.YYYY", key=kk,
                                                   label_visibility="collapsed", disabled=not use))
                    elif f == "historique":
                        val = st.text_input("Historique", v, key=f"{k0}_h{i}_{nc.norm(ev_name)[:20]}", label_visibility="collapsed", disabled=not use)
                    else:
                        val = st.text_area(nc.LABELS.get(f, f), v, key=kk, label_visibility="collapsed", disabled=not use,
                                           height=68 if len(v) < 90 else 110)
                    cur = (cur_c.get(f) or "").strip() if target != NEW and f != "historique" else ""
                    if cur:
                        st.markdown((f"<div class='nw-note'>s'ajoute à : {nc.e(cur[:110])}</div>" if f in nc.APPEND_FIELDS
                                     else f"<div class='nw-note'>remplace : {nc.e(cur[:110])}</div>"), unsafe_allow_html=True)
                    if use and (val or "").strip():
                        n_items += 1
                        if f == "historique":
                            h = val
                        else:
                            fields[f] = val
            who = {"prenom": pr, "nom": no} if target == NEW else cur_c
            sub = " · ".join(x for x in (nc.study_line(cur_c), nc.job_line(cur_c)) if x) if target != NEW else ""
            badge = ("<span class='chip chip--assoc'><i class='ph ph-user-plus'></i> Nouveau contact</span>" if target == NEW
                     else "<span class='chip'><i class='ph ph-user-check'></i> Dans ton réseau</span>")
            head.markdown(
                "<div class='nc-head'><div class='nc-avatar'>" + nc.e(nc.initials(who)) + "</div><div class='nc-id'>"
                f"<div class='nc-name'>{nc.e(who.get('prenom', ''))} <b>{nc.e((who.get('nom') or '').upper())}</b></div>"
                + (f"<div class='nc-sub'>{nc.e(sub)}</div>" if sub else "") + "</div></div>"
                f"<div class='nc-chips'>{badge}<span class='chip'><i class='ph ph-check-circle'></i> {n_items} info(s) à enregistrer</span></div>",
                unsafe_allow_html=True)
            plan.append((target, pr, no, fields, h))
        c1, c2 = st.columns(2)
        if c1.button("Enregistrer", type="primary", key=f"{k0}_save", disabled=not plan):
            done, errs = [], []
            for target, pr, no, fields, h in plan:
                try:
                    if target == NEW:
                        if not (pr.strip() or no.strip()):
                            errs.append("un nouveau contact sans prénom ni nom a été ignoré")
                            continue
                        c = nc.new_contact(prenom=pr, nom=no, rencontre_ou=ev_name, date_rencontre=news["date"],
                                           dernier_contact=news["date"], historique=h, **fields)
                        store.add(c)
                        done.append(f"{c['prenom']} {c['nom'].upper()} (nouveau)")
                    else:
                        ch = nc.news_changes(by_id[target], fields, h, news["date"])
                        if ch:
                            store.update(target, ch)
                            done.append(contact_label(target).split(" · ")[0])
                except Exception as ex:
                    errs.append(f"{contact_label(target)} : {ex}")
            refresh()
            st.session_state.pop("news", None)
            st.session_state.pop("news_txt", None)
            st.session_state.news_round = rnd + 1
            st.session_state.news_msg = (done, errs)
            st.rerun()
        if c2.button("Annuler", key=f"{k0}_cancel"):
            st.session_state.pop("news", None)
            st.rerun()
    msg = st.session_state.pop("news_msg", None)
    if msg:
        done, errs = msg
        if done:
            st.success("Enregistré : " + ", ".join(done) + ". Reporté dans l'Excel à la prochaine synchro.")
        for er in errs:
            st.error(er)


# =============================================================================
# 6. RÉSEAU (recherche + fiches modifiables)
# =============================================================================
def edit_form(c, key):
    with st.form(f"edit_{key}", border=False):
        c1, c2 = st.columns(2)
        prenom = c1.text_input("Prénom", c["prenom"])
        nom = c2.text_input("Nom", c["nom"])
        cat = st.selectbox("Catégorie", ["—"] + CAT_NAMES, index=(CAT_NAMES.index(c["categorie"]) + 1) if c["categorie"] in CAT_NAMES else 0)
        sj = study_job_fields(c, f"ed_{key}")
        sj["associations"] = assoc_field(c, f"ed_{key}")
        raconte = st.text_area("Personnalité, relation", c["raconte"], height=80)
        projets = st.text_area("Projets d'avenir", c.get("projets", ""), height=70)
        conseil = st.text_area("Conseil qu'il m'a donné (ou citation)", c.get("conseil", ""), height=70)
        anecdote = st.text_area("Anecdote / phrase marquante", c["anecdote"], height=70)
        c1, c2 = st.columns(2)
        hobbies = c1.text_input("Hobbies, sport", c["hobbies"])
        communs = c2.text_input("Points communs", c["points_communs"])
        utile = st.text_input("Valeur ajoutée dans mon réseau", c["utile_pour"])
        relation = st.selectbox("Relation", ["—"] + nc.RELATIONS, index=(nc.RELATIONS.index(c["relation"]) + 1) if c.get("relation") in nc.RELATIONS else 0)
        tache = st.text_input("Tâche à faire", c["tache"])
        c1, c2 = st.columns(2)
        ech = c1.date_input("Échéance", value=nc.parse_date(c["echeance"]), format="DD.MM.YYYY")
        dern = c2.date_input("Dernier contact", value=nc.parse_date(c["dernier_contact"]), format="DD.MM.YYYY")
        c1, c2 = st.columns(2)
        tel = c1.text_input("Numéro", c["telephone"])
        li = c2.text_input("Lien LinkedIn", c["linkedin"])
        if st.form_submit_button("Enregistrer les modifications"):
            save_update(c["id"], dict(prenom=prenom.strip(), nom=nom.strip(), categorie="" if cat == "—" else cat, **sj,
                                      anecdote=anecdote, conseil=conseil, raconte=raconte, projets=projets, hobbies=hobbies, points_communs=communs, utile_pour=utile,
                                      relation="" if relation == "—" else relation, tache=tache, echeance=nc.iso(ech),
                                      dernier_contact=nc.iso(dern), telephone=tel, linkedin=li))
            st.rerun()


def photo_box(c):
    """Photo du contact : capture de son profil LinkedIn ou photo de ta galerie. Reste dans l'app (pas dans l'Excel)."""
    cid = c["id"]
    up = st.file_uploader("Photo (capture de son profil LinkedIn, ou photo)", type=["jpg", "jpeg", "png", "webp"], key=f"ph_{cid}")
    b1, b2 = st.columns(2)
    if up is not None and b1.button("Enregistrer la photo", key=f"phs_{cid}", type="primary"):
        ok_ph = False
        try:
            store.set_photo(cid, nc.make_thumb(up.getvalue()))
            refresh()
            st.toast("Photo enregistrée", icon="✅")
            ok_ph = True
        except Exception as ex:
            st.error(f"Photo impossible à enregistrer : {ex}")
        if ok_ph:
            st.rerun()
    if photos.get(cid) and b2.button("Retirer la photo", key=f"phd_{cid}"):
        ok_ph = False
        try:
            store.set_photo(cid, "")
            refresh()
            ok_ph = True
        except Exception as ex:
            st.error(f"Échec : {ex}")
        if ok_ph:
            st.rerun()


with tab_net:
    q = st.text_input("Rechercher", placeholder="Nom, banque, anecdote, hobby…", key="q")
    inst_opts = nc.institutions(contacts)
    inst_count = dict(inst_opts)
    c1, c2 = st.columns(2)
    insts = c1.multiselect("Institution", [i for i, _ in inst_opts], key="f_inst", format_func=lambda i: f"{i} ({inst_count.get(i, 0)})",
                           placeholder="UBS, GSEM, HEC Lausanne…")
    cats = c2.multiselect("Catégories", CAT_NAMES, key="f_cat")
    c1, c2 = st.columns(2)
    rels = c1.multiselect("Relation", nc.RELATIONS, key="f_rel")
    assocs = c2.multiselect("Associations", ASSOC_OPTS, key="f_assoc")
    found = nc.search(contacts, q, cats, insts, rels, assocs)
    st.markdown(f"<div class='section-title'>Contacts <span class='count'>{len(found)}</span></div>", unsafe_allow_html=True)
    st.caption("Copie de ton Excel, qui fait foi. Tes ajouts et modifications y sont reportés à la prochaine synchro (double-clic sur Synchroniser_Network).")
    if not contacts:
        st.markdown("<div class='hint'>Ton réseau est vide pour l'instant : ajoute ta première rencontre dans l'onglet Ajouter.</div>", unsafe_allow_html=True)
    elif not found:
        st.markdown("<div class='hint'>Aucun contact ne correspond.</div>", unsafe_allow_html=True)
    lim = st.session_state.get("lim", 30)
    for c in found[:lim]:
        st.markdown(nc.contact_card_html(c, today, photo=photos.get(c["id"], ""), collapsible=True), unsafe_allow_html=True)
        if st.toggle("Modifier", key=f"tg_{c['id']}"):
            edit_form(c, c["id"])
            photo_box(c)
    if len(found) > lim:
        if st.button(f"Afficher plus ({len(found) - lim} restants)"):
            st.session_state.lim = lim + 30
            st.rerun()


# =============================================================================
# 7. À RELANCER
# =============================================================================
def relance_block(title, items, kind, open_rows=False):
    st.markdown(f"<div class='section-title'>{title} <span class='count'>{len(items)}</span></div>", unsafe_allow_html=True)
    if not items:
        st.markdown("<div class='hint'>Rien ici.</div>", unsafe_allow_html=True)
        return
    for c in items:
        ech = nc.parse_date(c["echeance"])
        late_days = (today - ech).days if ech and ech < today else 0
        when = ech.strftime("%d.%m") + (f" · {late_days} j de retard" if late_days else "")
        task = " ".join(str(c.get("tache") or "").split())
        label = f"**{when}** — {c['prenom']} {c['nom'].upper()} · {task[:70] + ('…' if len(task) > 70 else '')}"
        with st.expander(label, expanded=open_rows):
            st.markdown(f"<div class='nc-task {'late' if late_days else ''}'><i class='ph ph-check-square'></i> {nc.e(task)} · {nc.fr_date(ech)}</div>",
                        unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if b1.button("✓ Fait aujourd'hui", key=f"act_done_{kind}_{c['id']}", use_container_width=True):
                save_update(c["id"], dict(tache="", echeance="", dernier_contact=today.isoformat()), "Relance notée")
                st.rerun()
            base = max(ech or today, today)
            if b2.button("Reporter de 7 jours", key=f"act_snooze_{kind}_{c['id']}", use_container_width=True):
                save_update(c["id"], dict(echeance=(base + timedelta(days=7)).isoformat()), "Reporté de 7 jours")
                st.rerun()
            st.markdown(nc.contact_card_html(c, today, photo=photos.get(c["id"], ""), collapsible=True), unsafe_allow_html=True)


# =============================================================================
# 7 bis. ÉVÉNEMENT : qui je vais croiser et ce que j'ai à faire avec eux
# =============================================================================
with tab_ev:
    st.markdown("<div class='hint' style='text-align:left'>Tu vas à un événement ? Choisis les associations présentes : "
                "tu vois qui tu vas croiser, avec tes tâches en cours en premier, puis les personnes que tu n'as pas vues depuis longtemps.</div>",
                unsafe_allow_html=True)
    ev_assocs = st.multiselect("Associations présentes", ASSOC_OPTS, key="ev_assocs", placeholder="GUIC, IFSA…")
    if ev_assocs:
        todo_c, rest_c, n_late = nc.event_view(contacts, ev_assocs, today)
        st.markdown(nc.kpi_html([("Personnes", len(todo_c) + len(rest_c), "var(--blue-300)"),
                                 ("Tâches", len(todo_c), "var(--amber)"), ("En retard", n_late, "var(--red)")]), unsafe_allow_html=True)

        def ev_row(c, show_task):
            lt = nc.last_touch(c)
            note = f"Vu le {nc.fr_date(lt)}" if lt else "Jamais revu"
            st.markdown(nc.contact_card_html(c, today, photo=photos.get(c["id"], ""), collapsible=True, note=note), unsafe_allow_html=True)

        st.markdown(f"<div class='section-title'>À faire avec eux <span class='count'>{len(todo_c)}</span></div>", unsafe_allow_html=True)
        if not todo_c:
            st.markdown("<div class='hint'>Aucune tâche en cours avec ces personnes.</div>", unsafe_allow_html=True)
        for c in todo_c:
            ev_row(c, True)
        st.markdown(f"<div class='section-title'>Les autres, du moins revu au plus récent <span class='count'>{len(rest_c)}</span></div>",
                    unsafe_allow_html=True)
        for c in rest_c:
            ev_row(c, False)

with tab_rel:
    st.markdown("<div class='hint' style='text-align:left'>Seulement les tâches avec une échéance. Clique sur une ligne pour la déplier.</div>",
                unsafe_allow_html=True)
    relance_block("En retard", late, "late")
    relance_block("Cette semaine", week, "week")
    relance_block("Plus tard", later, "later")
