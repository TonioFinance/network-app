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
.nc { padding: 16px 18px; }
.nc-head { display: flex; align-items: center; gap: 14px; }
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
.nc-met { color: var(--text-dim); font-size: 12px; font-weight: 700; margin-top: 10px; text-transform: uppercase; letter-spacing: 0.8px; }
.nc-quote { margin-top: 10px; padding: 10px 12px; border-left: 3px solid var(--blue-500); background: rgba(37,99,235,0.08); border-radius: 0 12px 12px 0; color: #E2E8F0; font-style: italic; font-size: 14px; }
.nc-fact { display: flex; gap: 8px; margin-top: 8px; color: #CBD5E1; font-size: 14px; }
.nc-fact i { color: var(--blue-400); font-size: 17px; margin-top: 1px; }
.nc-task { margin-top: 10px; padding: 8px 12px; border-radius: 12px; font-size: 13px; font-weight: 700; color: var(--amber); background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.25); }
.nc-task.late { color: var(--red); background: rgba(225,29,72,0.10); border-color: rgba(225,29,72,0.3); }
.nc-foot { margin-top: 10px; color: var(--text-dim); font-size: 12px; }

@media (max-width: 768px) {
  .page-title { font-size: 32px; }
  [role="tablist"] { gap: 4px; padding: 5px 6px; }
  [role="tab"] { padding: 0 10px !important; }
  [role="tab"] p { font-size: 12px !important; }
  [data-testid="stForm"] { padding: 12px !important; }
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

tab_add, tab_net, tab_rel = st.tabs(["Ajouter", "Réseau", "À relancer"])

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
        anecdote = st.text_area("Anecdote / phrase marquante", placeholder="La phrase drôle, le détail niche qu'il t'a raconté…", height=90)
        conseil = st.text_area("Conseil qu'il m'a donné (ou citation)", placeholder="Un conseil sur le métier, la carrière, la vie… ou une phrase à retenir", height=90)
        raconte = st.text_area("Ce qu'il m'a raconté", placeholder="Son parcours, son équipe…", height=90)
        c1, c2 = st.columns(2)
        hobbies = c1.text_input("Sport, hobbies", placeholder="Trail, ski, échecs…")
        communs = c2.text_input("Points communs", placeholder="Même école, même club…")
        utile = st.text_input("Utile pour…", placeholder="Conseils CV, intro à son équipe, stage…")
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
                               date_rencontre=quand, anecdote=anecdote, conseil=conseil, raconte=raconte, hobbies=hobbies, points_communs=communs,
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
        anecdote = st.text_area("Anecdote / phrase marquante", c["anecdote"], height=80)
        conseil = st.text_area("Conseil qu'il m'a donné (ou citation)", c.get("conseil", ""), height=80)
        raconte = st.text_area("Ce qu'il m'a raconté", c["raconte"], height=80)
        c1, c2 = st.columns(2)
        hobbies = c1.text_input("Sport, hobbies", c["hobbies"])
        communs = c2.text_input("Points communs", c["points_communs"])
        utile = st.text_input("Utile pour…", c["utile_pour"])
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
                                      anecdote=anecdote, conseil=conseil, raconte=raconte, hobbies=hobbies, points_communs=communs, utile_pour=utile,
                                      relation="" if relation == "—" else relation, tache=tache, echeance=nc.iso(ech),
                                      dernier_contact=nc.iso(dern), telephone=tel, linkedin=li))
            st.rerun()


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
    if not contacts:
        st.markdown("<div class='hint'>Ton réseau est vide pour l'instant : ajoute ta première rencontre dans l'onglet Ajouter.</div>", unsafe_allow_html=True)
    elif not found:
        st.markdown("<div class='hint'>Aucun contact ne correspond.</div>", unsafe_allow_html=True)
    lim = st.session_state.get("lim", 30)
    for c in found[:lim]:
        label = f"{c['prenom']} {c['nom'].upper()}" + (f" · {c['institution']}" if c["institution"] else "")
        with st.expander(label):
            st.markdown(nc.contact_card_html(c, today), unsafe_allow_html=True)
            if st.toggle("Modifier", key=f"tg_{c['id']}"):
                edit_form(c, c["id"])
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
        st.markdown(nc.contact_card_html(c, today), unsafe_allow_html=True)
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
