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


def inject_css():
    root = ":root{" + "".join(f"--{k}:{v};" for k, v in TOKENS.items()) + "}"
    st.markdown(f"<style>{root}{CSS}</style>", unsafe_allow_html=True)


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
late, week, silent = nc.relances(contacts, today)

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

tab_add, tab_news, tab_net, tab_rel = st.tabs(["Ajouter", "Nouvelles", "Réseau", "À relancer"])

CAT_NAMES = [c for c, _ in nc.CATEGORIES]


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
with tab_add:
    with st.form("add", clear_on_submit=True, border=True):
        c1, c2 = st.columns(2)
        prenom = c1.text_input("Prénom *", placeholder="Prénom")
        nom = c2.text_input("Nom *", placeholder="Nom")
        cat = choice("Catégorie", CAT_NAMES, key="add_cat")
        c1, c2 = st.columns(2)
        inst = c1.text_input("Institution / école", placeholder="Pictet, UNIGE, HEC…")
        poste = c2.text_input("Poste ou filière", placeholder="Analyst, MSc Finance 2e année…")
        c1, c2 = st.columns([3, 2])
        ou = c1.text_input("Rencontré où", placeholder="Wick, soirée GUIC, cours…")
        quand = c2.date_input("Quand", value=today, format="DD.MM.YYYY")
        raconte = st.text_area("Personnalité, relation", placeholder="Comment il fonctionne, son caractère, comment vous vous entendez, son parcours…", height=90)
        projets = st.text_area("Projets d'avenir", placeholder="Master visé, poste rêvé, création de boîte, départ à l'étranger…", height=80)
        c1, c2 = st.columns(2)
        hobbies = c1.text_input("Hobbies, sport", placeholder="Trail, ski, échecs…")
        communs = c2.text_input("Points communs", placeholder="Même école, même club…")
        conseil = st.text_area("Conseil qu'il m'a donné (ou citation)", placeholder="Un conseil sur le métier, la carrière, la vie… ou une phrase à retenir", height=80)
        anecdote = st.text_area("Anecdote / phrase marquante", placeholder="La phrase drôle, le détail niche qu'il t'a raconté…", height=80)
        utile = st.text_input("Valeur ajoutée dans mon réseau", placeholder="Regard d'expert sur le PE, porte d'entrée chez Pictet, bon conseil carrière…")
        relation = choice("Relation", nc.RELATIONS, key="add_rel", default="Network")
        with st.expander("Suivi et coordonnées"):
            tache = st.text_input("Tâche à faire", placeholder="Lui écrire sur LinkedIn, envoyer le CV…")
            c1, c2 = st.columns(2)
            ech = c1.date_input("Échéance", value=None, format="DD.MM.YYYY")
            tel = c2.text_input("Numéro", placeholder="+41 …")
            li = st.text_input("Lien LinkedIn", placeholder="https://www.linkedin.com/in/…")
        ok = st.form_submit_button("Enregistrer")
    if ok:
        if not prenom.strip() or not nom.strip():
            st.error("Il faut au moins le prénom et le nom.")
        else:
            dup = nc.duplicates(contacts, prenom, nom)
            c = nc.new_contact(prenom=prenom, nom=nom, categorie=cat or "", institution=inst, poste=poste, rencontre_ou=ou,
                               date_rencontre=quand, anecdote=anecdote, conseil=conseil, raconte=raconte, projets=projets, hobbies=hobbies, points_communs=communs,
                               utile_pour=utile, relation=relation or "", tache=tache, echeance=ech, dernier_contact=quand,
                               telephone=tel, linkedin=li)
            try:
                store.add(c)
                refresh()
                st.toast(f"{c['prenom']} {c['nom'].upper()} ajouté(e)", icon="✅")
                if dup:
                    st.warning(f"Il y avait déjà un(e) {c['prenom']} {c['nom'].upper()} dans ton réseau : vérifie le doublon dans l'onglet Réseau.")
            except Exception as ex:
                st.error(f"Échec de l'enregistrement : {ex}")


# =============================================================================
# 5 bis. NOUVELLES (texte libre rangé par Gemini, validé avant enregistrement)
# =============================================================================
GEMINI_KEY = secret("GEMINI_API_KEY") or secret("gemini_api_key")
NEW, SKIP = "__new__", "__skip__"
by_id = {c["id"]: c for c in contacts}


def contact_label(x):
    if x == NEW:
        return "➕ Nouveau contact"
    if x == SKIP:
        return "Ignorer cette personne"
    c = by_id.get(x, {})
    return f"{c.get('prenom', '')} {c.get('nom', '').upper()}" + (f" · {c['institution']}" if c.get("institution") else "")


with tab_news:
    st.markdown("<div class='hint' style='text-align:left'>Choisis la ou les personnes (tape quelques lettres), puis écris ou dicte "
                "ce qu'elles t'ont appris et ce que tu dois faire. L'IA range chaque info dans la bonne case, reformule et devine "
                "l'événement. Tu valides avant d'enregistrer : les textes s'ajoutent à la suite, rien n'est écrasé.</div>", unsafe_allow_html=True)
    if not GEMINI_KEY:
        st.warning("Ajoute GEMINI_API_KEY dans les Secrets de l'app (Streamlit Cloud → Settings → Secrets) pour activer l'analyse.")
    rnd = st.session_state.setdefault("news_round", 0)
    with st.form(f"news_in_{rnd}", border=True):
        people_ids = [c["id"] for c in sorted(contacts, key=lambda c: (nc.norm(c["prenom"]), nc.norm(c["nom"])))]
        c1, c2 = st.columns([3, 2])
        picked = c1.multiselect("Personnes", people_ids, format_func=contact_label, placeholder="Tape « dio », « pictet »…")
        ev_date = c2.date_input("Date", value=today, format="DD.MM.YYYY")
        txt = st.text_area("Ce qu'ils t'ont appris, ce que tu dois faire", height=180,
                           placeholder="Kylian : passé chez Cabelo, conseille de postuler aux stages d'été dès janvier. Café mi-novembre.")
        go = st.form_submit_button("Analyser", disabled=not GEMINI_KEY)
    if go and txt.strip():
        with st.spinner("Analyse en cours…"):
            try:
                sel = [by_id[x] for x in picked if x in by_id]
                res, model = nc.gemini_json(nc.news_prompt(txt, contacts, today.isoformat(), ev_date.isoformat(), sel),
                                            GEMINI_KEY, secret("gemini_model") or None)
                props = nc.clean_proposal(res, contacts)
                if len(sel) == 1 and len(props) == 1 and not props[0]["contact_id"]:
                    props[0]["contact_id"] = sel[0]["id"]          # une seule personne choisie : c'est elle
                st.session_state.news = dict(props=props, date=ev_date.isoformat(), name=str((res or {}).get("evenement") or ""),
                                             model=model, n=st.session_state.get("news_n", 0) + 1)
                st.session_state.news_n = st.session_state.news["n"]
            except Exception as ex:
                st.error(f"Analyse impossible : {ex}. Ton texte reste dans la zone ci-dessus.")

    news = st.session_state.get("news")
    if news:
        props, k0 = news["props"], f"nw{news['n']}"
        ev_name = st.text_input("Événement (deviné, modifiable)", news["name"], key=f"{k0}_ev", placeholder="Soirée alumni, coffee chat…")
        if not props:
            st.info("Aucune personne repérée dans le texte.")
        others = [c["id"] for c in sorted(contacts, key=lambda c: (nc.norm(c["prenom"]), nc.norm(c["nom"])))]
        plan = []
        for i, p in enumerate(props):
            name = f"{p['prenom']} {p['nom'].upper()}".strip() or "Personne"
            st.markdown(f"<div class='section-title'>{nc.e(name)}</div>", unsafe_allow_html=True)
            if p["doute"]:
                st.warning(p["doute"])
            first = ([p["contact_id"]] if p["contact_id"] else []) + [x for x in p["candidats"] if x != p["contact_id"]]
            opts = first + [NEW, SKIP] + [x for x in others if x not in first]
            default = first[0] if first else NEW
            target = st.selectbox("Contact", opts, index=opts.index(default), key=f"{k0}_t{i}", format_func=contact_label)
            if target == SKIP:
                continue
            pr, no = p["prenom"], p["nom"]
            if target == NEW:
                c1, c2 = st.columns(2)
                pr = c1.text_input("Prénom", p["prenom"], key=f"{k0}_p{i}")
                no = c2.text_input("Nom", p["nom"], key=f"{k0}_n{i}")
            cur_c = by_id.get(target, {})
            fields = {}
            for f, v in p["champs"].items():
                cur = (cur_c.get(f) or "").strip()
                use = st.checkbox(nc.LABELS.get(f, f), value=True, key=f"{k0}_u{i}_{f}")
                if f == "echeance":
                    val = st.date_input("Échéance", value=nc.parse_date(v), format="DD.MM.YYYY", key=f"{k0}_v{i}_{f}",
                                        label_visibility="collapsed")
                    val = nc.iso(val)
                else:
                    val = st.text_area(nc.LABELS.get(f, f), v, key=f"{k0}_v{i}_{f}", label_visibility="collapsed",
                                       height=68 if len(v) < 90 else 110)
                if cur and target != NEW:
                    st.caption(("Ajouté à la suite de : " if f in nc.APPEND_FIELDS else "Remplace : ") + cur[:140])
                if use and (val or "").strip():
                    fields[f] = val
            h = st.text_input("Historique", nc.hist_line(news["date"], ev_name, p["historique"]), key=f"{k0}_h{i}_{nc.norm(ev_name)[:20]}")
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
        c1, c2 = st.columns(2)
        inst = c1.text_input("Institution / école", c["institution"])
        poste = c2.text_input("Poste ou filière", c["poste"])
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
            save_update(c["id"], dict(prenom=prenom.strip(), nom=nom.strip(), categorie="" if cat == "—" else cat, institution=inst, poste=poste,
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
        try:
            store.set_photo(cid, nc.make_thumb(up.getvalue()))
            refresh()
            st.toast("Photo enregistrée", icon="✅")
            st.rerun()
        except Exception as ex:
            st.error(f"Photo impossible à enregistrer : {ex}")
    if photos.get(cid) and b2.button("Retirer la photo", key=f"phd_{cid}"):
        try:
            store.set_photo(cid, "")
            refresh()
            st.rerun()
        except Exception as ex:
            st.error(f"Échec : {ex}")


with tab_net:
    q = st.text_input("Rechercher", placeholder="Nom, banque, anecdote, hobby…", key="q")
    inst_opts = nc.institutions(contacts)
    inst_count = dict(inst_opts)
    c1, c2 = st.columns(2)
    insts = c1.multiselect("Institution", [i for i, _ in inst_opts], key="f_inst", format_func=lambda i: f"{i} ({inst_count.get(i, 0)})",
                           placeholder="JP Morgan, GSEM, UBS…")
    cats = c2.multiselect("Catégories", CAT_NAMES, key="f_cat")
    rels = st.multiselect("Relation", nc.RELATIONS, key="f_rel")
    found = nc.search(contacts, q, cats, insts, rels)
    st.markdown(f"<div class='section-title'>Contacts <span class='count'>{len(found)}</span></div>", unsafe_allow_html=True)
    st.caption("Copie de ton Excel, qui fait foi. Tes ajouts et modifications y sont reportés à la prochaine synchro (21h30 ou double-clic sur Synchroniser_Network).")
    if not contacts:
        st.markdown("<div class='hint'>Ton réseau est vide pour l'instant : ajoute ta première rencontre dans l'onglet Ajouter.</div>", unsafe_allow_html=True)
    elif not found:
        st.markdown("<div class='hint'>Aucun contact ne correspond.</div>", unsafe_allow_html=True)
    lim = st.session_state.get("lim", 30)
    for c in found[:lim]:
        label = f"{c['prenom']} {c['nom'].upper()}" + (f" · {c['institution']}" if c["institution"] else "")
        with st.expander(label):
            st.markdown(nc.contact_card_html(c, today, photo=photos.get(c["id"], "")), unsafe_allow_html=True)
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
def relance_block(title, items, kind):
    st.markdown(f"<div class='section-title'>{title} <span class='count'>{len(items)}</span></div>", unsafe_allow_html=True)
    if not items:
        st.markdown("<div class='hint'>Rien ici.</div>", unsafe_allow_html=True)
        return
    for c in items:
        st.markdown(nc.contact_card_html(c, today, photo=photos.get(c["id"], "")), unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("✓ Fait aujourd'hui", key=f"act_done_{kind}_{c['id']}"):
            save_update(c["id"], dict(tache="", echeance="", dernier_contact=today.isoformat()), "Relance notée")
            st.rerun()
        base = max(nc.parse_date(c["echeance"]) or today, today)
        if b2.button("Reporter de 7 jours", key=f"act_snooze_{kind}_{c['id']}"):
            save_update(c["id"], dict(echeance=(base + timedelta(days=7)).isoformat(), tache=c["tache"] or "Prendre des nouvelles"), "Reporté de 7 jours")
            st.rerun()


with tab_rel:
    relance_block("En retard", late, "late")
    relance_block("Cette semaine", week, "week")
