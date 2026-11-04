"""Logique de l'app Network (sans Streamlit) : colonnes, stockage Google Sheet ou CSV local, relances, cartes HTML.

Le Google Sheet a deux onglets, créés automatiquement : « Saisies » (journal de ce qui est saisi dans l'app)
et « Réseau » (copie de l'Excel, que l'app affiche). L'Excel prévaut : voir importer_network.py.
"""
from __future__ import annotations

import csv
import html
import json
import re
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------- colonnes du Google Sheet
COLUMNS = [
    "id", "cree_le", "prenom", "nom", "categorie", "institution", "poste", "rencontre_ou", "date_rencontre",
    "anecdote", "raconte", "hobbies", "points_communs", "utile_pour", "chaleur", "tache", "echeance",
    "dernier_contact", "telephone", "linkedin", "importe", "relation", "conseil", "historique", "projets",
    "ecole", "niveau", "etudes", "employeur", "fonction", "associations",
]
LABELS = {
    "prenom": "Prénom", "nom": "Nom", "categorie": "Catégorie", "institution": "Institution / école",
    "poste": "Poste ou filière", "rencontre_ou": "Rencontré où", "date_rencontre": "Date de la rencontre",
    "anecdote": "Anecdote / phrase marquante", "raconte": "Personnalité, relation", "hobbies": "Hobbies, sport",
    "points_communs": "Points communs", "utile_pour": "Valeur ajoutée dans mon réseau", "chaleur": "Chaleur du contact",
    "tache": "Tâche à faire", "echeance": "Échéance", "dernier_contact": "Dernier contact",
    "telephone": "Numéro", "linkedin": "Lien LinkedIn", "relation": "Relation",
    "conseil": "Conseil qu'il m'a donné", "historique": "Historique", "projets": "Projets d'avenir",
    "ecole": "École / faculté", "niveau": "Niveau d'études", "etudes": "Études", "employeur": "Employeur", "fonction": "Poste", "associations": "Associations",
}

# Catégories : (nom, icône Phosphor). Le premier groupe = pro, le second = études et perso.
CATEGORIES = [
    ("Banque privée / Wealth management", "ph-bank"),
    ("Asset management / Fonds", "ph-chart-line-up"),
    ("Private markets (PE, VC, dette privée)", "ph-rocket-launch"),
    ("Family office / Gérant indépendant", "ph-house-line"),
    ("Banque d'investissement / M&A", "ph-handshake"),
    ("Trading / Commodities", "ph-swap"),
    ("Audit / Conseil", "ph-magnifying-glass"),
    ("Recruteur / RH", "ph-identification-badge"),
    ("Fintech / Startup", "ph-lightning"),
    ("Étudiant Bachelor", "ph-student"),
    ("Étudiant Master", "ph-graduation-cap"),
    ("Alumni", "ph-users-three"),
    ("Professeur / Chercheur", "ph-book-open"),
    ("Club / Association", "ph-flag"),
    ("Perso / Amis", "ph-heart"),
]
CAT_ICON = dict(CATEGORIES)
RELATIONS = ["Network", "Ami", "À contacter"]
NIVEAUX = ["B1", "B2", "B3", "Bachelor obtenu", "M1", "M2", "Doctorat"]
ETUDES = ["En cours", "Terminées"]
ASSOCIATIONS = ["GUIC", "Alumni GUIC", "Comité GSEM", "IFSA"]   # proposées par défaut ; on peut en ajouter d'autres


def assoc_list(c) -> list:
    return [a.strip() for a in re.split(r"[,;]", str(c.get("associations") or "")) if a.strip()]


def all_associations(contacts) -> list:
    seen = {norm(a).strip(): a for a in ASSOCIATIONS}
    for c in contacts:
        for a in assoc_list(c):
            seen.setdefault(norm(a).strip(), a)
    return list(seen.values())
CHALEURS = ["Chaud", "Tiède", "Froid"]
CHALEUR_CLS = {"Chaud": "hot", "Tiède": "warm", "Froid": "cold"}
SANS_NOUVELLES_JOURS = 45          # « À relancer » : contact chaud ou tiède sans nouvelles depuis ce nombre de jours


# --------------------------------------------------------------------------- dates
def parse_date(s) -> date | None:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    s = str(s).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def iso(d) -> str:
    d = parse_date(d)
    return d.isoformat() if d else ""


MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def fr_date(d) -> str:
    d = parse_date(d)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}" if d else ""


def new_contact(**fields) -> dict:
    c = {k: "" for k in COLUMNS}
    c.update({k: ("" if v is None else str(v).strip()) for k, v in fields.items() if k in c})
    c["id"] = c["id"] or uuid.uuid4().hex[:10]
    c["cree_le"] = c["cree_le"] or datetime.now().strftime("%Y-%m-%d %H:%M")
    for k in ("date_rencontre", "echeance", "dernier_contact"):
        c[k] = iso(c[k])
    c["nom"] = c["nom"].strip()
    c["prenom"] = c["prenom"].strip()
    return c


# --------------------------------------------------------------------------- stockage
class CsvStore:
    """Stockage local (tests, ou usage sans Google). Fichier CSV avec les colonnes COLUMNS."""

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", newline="", encoding="utf8") as f:
                csv.writer(f).writerow(COLUMNS)

    def all(self) -> list[dict]:
        with self.path.open(newline="", encoding="utf8") as f:
            return [{k: (r.get(k) or "") for k in COLUMNS} for r in csv.DictReader(f)]

    def _write(self, rows):
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, self.path)

    def add(self, c: dict):
        rows = self.all()
        rows.append({k: c.get(k, "") for k in COLUMNS})
        self._write(rows)

    def update(self, cid: str, changes: dict):
        rows = self.all()
        for r in rows:
            if r["id"] == cid:
                r.update({k: v for k, v in changes.items() if k in COLUMNS and k != "id"})
        self._write(rows)

    def delete(self, cid: str):
        self._write([r for r in self.all() if r["id"] != cid])

    # photos (mode local : fichier JSON à côté du CSV)
    def photos(self) -> dict:
        p = self.path.with_suffix(".photos.json")
        return json.loads(p.read_text(encoding="utf8")) if p.exists() else {}

    def set_photo(self, cid: str, b64: str):
        ph = self.photos()
        if b64:
            ph[cid] = b64
        else:
            ph.pop(cid, None)
        self.path.with_suffix(".photos.json").write_text(json.dumps(ph), encoding="utf8")


MIRROR_TAB = "Réseau"          # copie de l'Excel (réécrite à chaque synchro) : c'est ce que l'app affiche
JOURNAL_TAB = "Saisies"        # tout ce que tu as saisi dans l'app (ajouts et modifications), jamais réécrit
OLD_TAB = "Contacts"           # ancien onglet unique (avant la synchro avec l'Excel)
JOURNAL_HEAD = ["horodatage", "action", "statut", "changements"] + COLUMNS
A_SYNCHRONISER = "à synchroniser"
PHOTO_TAB = "Photos"           # petites photos des contacts (base64), propres à l'app


def _a1(row: int, col: int) -> str:
    letters = ""
    while col:
        col, r = divmod(col - 1, 26)
        letters = chr(65 + r) + letters
    return f"{letters}{row}"


def _records(vals, keys=COLUMNS, need_id=True) -> list:
    if not vals:
        return []
    head = vals[0]
    out = []
    for row in vals[1:]:
        r = {h: (row[i] if i < len(row) else "") for i, h in enumerate(head)}
        if not need_id or r.get("id"):
            out.append({k: r.get(k, "") for k in keys})
    return out


class SheetStore:
    """Google Sheet à deux onglets.
    « Saisies » : journal de tout ce qui est saisi dans l'app (ajout, modification), statut « à synchroniser » puis le résultat.
    « Réseau » : copie de l'onglet Network de l'Excel, réécrite à chaque synchro. L'app lit et affiche cet onglet.
    L'Excel prévaut : la synchro (importer_network.py) reporte les saisies dans l'Excel, puis recopie l'Excel dans « Réseau »."""

    def __init__(self, gc, sheet_id: str):
        self.sh = sh = gc.open_by_key(sheet_id)
        titles = [w.title for w in sh.worksheets()]
        reprise = []
        if OLD_TAB in titles:
            old = sh.worksheet(OLD_TAB)
            reprise = _records(old.get_all_values())
            if MIRROR_TAB not in titles:
                old.update_title(MIRROR_TAB)
            else:
                name = "Ancien onglet Contacts"
                if name in titles:
                    name += " " + datetime.now().strftime("%Y-%m-%d %Hh%M")
                old.update_title(name)
        self.ws = self._tab(MIRROR_TAB, COLUMNS)
        self.head = self._ensure_head(self.ws, COLUMNS)
        self.jws = self._tab(JOURNAL_TAB, JOURNAL_HEAD)
        self.jhead = self._ensure_head(self.jws, JOURNAL_HEAD)
        try:
            self.jws.update_index(0)
            self.ws.update_index(1)
        except Exception:
            pass
        if reprise:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.jws.append_rows([self._jrow(now, "ajout (reprise)", A_SYNCHRONISER, "", c) for c in reprise], value_input_option="RAW")

    # ---- outils
    def _tab(self, name, head):
        try:
            return self.sh.worksheet(name)
        except Exception:
            ws = self.sh.add_worksheet(title=name, rows=1000, cols=len(head))
            ws.update(range_name="A1", values=[head])
            return ws

    @staticmethod
    def _ensure_head(ws, cols):
        head = ws.row_values(1)
        if not head:
            ws.update(range_name="A1", values=[list(cols)])
            return list(cols)
        missing = [c for c in cols if c not in head]
        if missing:
            head = head + missing
            if ws.col_count < len(head):
                ws.add_cols(len(head) - ws.col_count)
            ws.update(range_name="A1", values=[head])
        return head

    def _jrow(self, when, action, statut, changements, c):
        vals = {"horodatage": when, "action": action, "statut": statut, "changements": changements}
        return [vals[h] if h in vals else ("" if c.get(h) is None else str(c.get(h, ""))) for h in self.jhead]

    def _journal(self, action, c, changements=""):
        self.jws.append_row(self._jrow(datetime.now().strftime("%Y-%m-%d %H:%M"), action, A_SYNCHRONISER, changements, c),
                            value_input_option="RAW")

    def _row_of(self, cid: str) -> int | None:
        ids = self.ws.col_values(self.head.index("id") + 1)
        return ids.index(cid) + 1 if cid in ids else None

    # ---- utilisé par l'app
    def all(self) -> list[dict]:
        return _records(self.ws.get_all_values())

    def add(self, c: dict):
        self.ws.append_row([c.get(h, "") for h in self.head], value_input_option="RAW")
        self._journal("ajout", c)

    def update(self, cid: str, changes: dict):
        r = self._row_of(cid)
        if not r:
            raise KeyError(cid)
        cur = self.ws.row_values(r)
        cur += [""] * (len(self.head) - len(cur))
        before = dict(zip(self.head, cur))
        diff = {}
        for k, v in changes.items():
            if k in self.head and k != "id":
                v = "" if v is None else str(v)
                if (before.get(k) or "") != v:
                    diff[k] = [before.get(k) or "", v]
                cur[self.head.index(k)] = v
        if not diff:
            return
        self.ws.update(range_name=f"A{r}", values=[cur], value_input_option="RAW")
        after = dict(zip(self.head, cur))
        self._journal("modification", after, json.dumps(diff, ensure_ascii=False))

    # ---- photos (onglet « Photos » : id | photo en base64 ; jamais dans l'Excel)
    def _photo_ws(self, create=False):
        try:
            return self.sh.worksheet(PHOTO_TAB)
        except Exception:
            if not create:
                return None
            ws = self.sh.add_worksheet(title=PHOTO_TAB, rows=200, cols=2)
            ws.update(range_name="A1", values=[["id", "photo"]])
            return ws

    def photos(self) -> dict:
        ws = self._photo_ws()
        if ws is None:
            return {}
        return {r[0]: r[1] for r in ws.get_all_values()[1:] if len(r) > 1 and r[0] and r[1]}

    def set_photo(self, cid: str, b64: str):
        ws = self._photo_ws(create=True)
        ids = ws.col_values(1)
        if cid in ids:
            ws.update(range_name=f"A{ids.index(cid) + 1}", values=[[cid, b64]], value_input_option="RAW")
        else:
            ws.append_row([cid, b64], value_input_option="RAW")

    # ---- utilisé par la synchro
    def journal(self) -> list:
        """[(numéro de ligne, saisie)] dans l'ordre chronologique."""
        vals = self.jws.get_all_values()
        recs = _records(vals, keys=JOURNAL_HEAD, need_id=False)
        return [(i + 2, r) for i, r in enumerate(recs) if any(r.values())]

    def mark(self, marks):
        """marks = [(ligne, statut)] : écrit le résultat de la synchro dans la colonne statut du journal."""
        if not marks:
            return
        col = self.jhead.index("statut") + 1
        self.jws.batch_update([{"range": _a1(r, col), "values": [[st]]} for r, st in marks], value_input_option="RAW")

    def replace_mirror(self, contacts: list):
        values = [list(COLUMNS)] + [[("" if c.get(k) is None else str(c.get(k, ""))) for k in COLUMNS] for c in contacts]
        if self.ws.row_count < len(values) + 10:
            self.ws.add_rows(len(values) + 10 - self.ws.row_count)
        if self.ws.col_count < len(COLUMNS):
            self.ws.add_cols(len(COLUMNS) - self.ws.col_count)
        self.ws.clear()
        self.ws.update(range_name="A1", values=values, value_input_option="RAW")
        self.head = list(COLUMNS)


# --------------------------------------------------------------------------- recherche et relances
def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


SEARCH_FIELDS = ["prenom", "nom", "institution", "poste", "categorie", "rencontre_ou", "anecdote", "conseil", "historique", "raconte", "projets", "ecole", "employeur", "fonction", "associations",
                 "hobbies", "points_communs", "utile_pour", "tache"]


def inst_tokens(s) -> list:
    """« GSEM / UBS » -> ['GSEM', 'UBS'] : une institution par morceau (séparateurs / , ; + & ·)."""
    out = []
    for part in re.split(r"[/,;+&·]|\bet\b", str(s or "")):
        part = part.strip()
        if part:
            out.append(part)
    return out


def inst_of(c) -> list:
    """Écoles et employeurs d'un contact (anciens champs « institution » si les nouveaux sont vides)."""
    toks = inst_tokens(c.get("ecole")) + inst_tokens(c.get("employeur"))
    return toks or [t for t in inst_tokens(c.get("institution")) if "préciser" not in t.lower()]


def study_line(c) -> str:
    base = " · ".join(x for x in (c.get("ecole"), c.get("niveau")) if x)
    if not c.get("etudes"):
        return base
    return f"{base} ({c['etudes'].lower()})" if base else f"Études {c['etudes'].lower()}"


def job_line(c) -> str:
    return " · ".join(x for x in (c.get("employeur"), c.get("fonction")) if x)


def institutions(contacts) -> list:
    """Liste (nom affiché, nombre de contacts), la plus fournie d'abord. Les variantes de casse sont regroupées."""
    count, label = {}, {}
    for c in contacts:
        for t in {norm(x).strip(): x for x in inst_of(c)}.items():
            count[t[0]] = count.get(t[0], 0) + 1
            label.setdefault(t[0], t[1])
    return sorted(((label[k], n) for k, n in count.items()), key=lambda x: (-x[1], norm(x[0])))


def search(contacts, q="", cats=None, insts=None, relations=None, assocs=None):
    words = norm(q).split()
    out = []
    for c in contacts:
        if cats and c["categorie"] not in cats:
            continue
        if insts:
            mine = {norm(x).strip() for x in inst_of(c)}
            if not mine & {norm(i).strip() for i in insts}:
                continue
        if relations and c.get("relation", "") not in relations:
            continue
        if assocs and not {norm(a).strip() for a in assoc_list(c)} & {norm(a).strip() for a in assocs}:
            continue
        blob = norm(" ".join(c.get(k, "") for k in SEARCH_FIELDS))
        if all(w in blob for w in words):
            out.append(c)
    return sorted(out, key=lambda c: (c.get("dernier_contact") or c.get("date_rencontre") or c.get("cree_le") or ""), reverse=True)


def last_touch(c) -> date | None:
    return parse_date(c.get("dernier_contact")) or parse_date(c.get("date_rencontre")) or parse_date((c.get("cree_le") or "")[:10])


def relances(contacts, today: date | None = None):
    """Seulement les tâches avec une échéance : en retard, dans les 7 jours, plus tard. Une tâche sans date n'apparaît pas ici."""
    today = today or date.today()
    late, week, later = [], [], []
    for c in contacts:
        ech = parse_date(c.get("echeance"))
        if not ech or not str(c.get("tache") or "").strip():
            continue
        (late if ech < today else week if ech <= today + timedelta(days=7) else later).append(c)
    for lst in (late, week, later):
        lst.sort(key=lambda c: c["echeance"])
    return late, week, later


def duplicates(contacts, prenom, nom):
    p, n = norm(prenom).strip(), norm(nom).strip()
    return [c for c in contacts if norm(c["prenom"]).strip() == p and norm(c["nom"]).strip() == n]


# --------------------------------------------------------------------------- HTML (aucune indentation en début de ligne : Markdown)
def e(s) -> str:
    return html.escape(str(s or ""))


def initials(c) -> str:
    return ((c.get("prenom") or "?")[:1] + (c.get("nom") or "")[:1]).upper()


def split_points(v: str) -> list:
    """Découpe un texte en points : séparateurs « · », « ; », retours à la ligne, puis phrases si c'est long."""
    parts = [p.strip(" .;·") for p in re.split(r"\s·\s|\s?;\s|\n", str(v or "")) if p.strip(" .;·")]
    out = []
    for p in parts:
        if len(p) > 90:
            out += [x.strip(" .") for x in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý])", p) if x.strip(" .")]
        else:
            out.append(p)
    return out


def _value_html(v, mode="points"):
    pts = split_points(v)
    if not pts:
        return ""
    if mode == "inline" or len(pts) == 1:
        return e(" · ".join(pts) if mode == "inline" else pts[0])
    return "<ul>" + "".join(f"<li>{e(p)}</li>" for p in pts) + "</ul>"


def contact_card_html(c, today: date | None = None, extra="", photo: str = "", collapsible: bool = False, note: str = "") -> str:
    """collapsible : seul l'en-tête (photo, nom, études/emploi, pastilles, tâche) est visible ; un clic déplie la fiche."""
    today = today or date.today()
    icon = CAT_ICON.get(c.get("categorie"), "ph-user")
    lines_sub = [x for x in (study_line(c), job_line(c)) if x]
    if not lines_sub:
        old = " · ".join(x for x in (c.get("institution"), c.get("poste")) if x)
        lines_sub = [old] if old else []
    sub = "<br>".join(e(x) for x in lines_sub)
    chips = []
    if c.get("categorie"):
        chips.append(f"<span class='chip'><i class='ph {icon}'></i> {e(c['categorie'])}</span>")
    if c.get("relation"):
        chips.append(f"<span class='chip'><i class='ph ph-tag'></i> {e(c['relation'])}</span>")
    for a in assoc_list(c):
        chips.append(f"<span class='chip chip--assoc'><i class='ph ph-users-three'></i> {e(a)}</span>")
    task = ""
    if c.get("tache") or c.get("echeance"):
        ech = parse_date(c.get("echeance"))
        cls = "late" if ech and ech < today else ""
        when = f" · {fr_date(ech)}" if ech else ""
        task = f"<div class='nc-task {cls}'><i class='ph ph-check-square'></i> {e(c.get('tache') or 'À faire')}{e(when)}</div>"
    met = " · ".join(x for x in (c.get("rencontre_ou"), fr_date(c.get("date_rencontre"))) if x)
    hist = [x.strip() for x in (c.get("historique") or "").split("\n") if x.strip()]
    hist_html = ""
    if hist:
        recent = hist[-4:][::-1]
        hist_html = "<ul>" + "".join(f"<li>{e(x)}</li>" for x in recent) + "</ul>"
        if len(hist) > 4:
            hist_html += f"<div class='nc-more'>+ {len(hist) - 4} plus ancien(s)</div>"
    todo = "<span class='nc-empty'>à découvrir</span>"
    rows = [
        ("ph-map-pin", "Rencontré", e(met) if met else "", ""),
        ("ph-user-focus", "Personnalité, relation", _value_html(c.get("raconte")), ""),
        ("ph-rocket-launch", "Projets d'avenir", _value_html(c.get("projets")) or todo, ""),
        ("ph-person-simple-run", "Hobbies", _value_html(c.get("hobbies"), "inline") or todo, ""),
        ("ph-link-simple", "Points communs", _value_html(c.get("points_communs"), "inline"), ""),
        ("ph-lightbulb", "Conseil", _value_html(c.get("conseil")), "quote"),
        ("ph-sparkle", "Anecdote", _value_html(c.get("anecdote")), ""),
        ("ph-clock-counter-clockwise", "Historique", hist_html, "small"),
        ("ph-star", "Valeur ajoutée", _value_html(c.get("utile_pour")), ""),
    ]
    body = "".join(f"<div class='nc-k'><i class='ph {ic}'></i>{e(k)}</div><div class='nc-v {cls}'>{v}</div>" for ic, k, v, cls in rows if v)
    lt = last_touch(c)
    foot = f"Dernier contact : {fr_date(lt)}" if lt else ""
    li = ""
    if c.get("linkedin"):
        li = f"<a class='nc-li' href='{e(c['linkedin'])}' target='_blank' rel='noopener'><i class='ph ph-linkedin-logo'></i></a>"
    head_html = "".join([
        "<div class='nc-head'>",
        (f"<div class='nc-avatar nc-photo'><img src='data:image/jpeg;base64,{photo}' alt=''></div>" if photo
         else f"<div class='nc-avatar'>{e(initials(c))}</div>"),
        "<div class='nc-id'>",
        f"<div class='nc-name'>{e(c.get('prenom'))} <b>{e((c.get('nom') or '').upper())}</b></div>",
        f"<div class='nc-sub'>{sub}</div>" if sub else "",
        "</div>", li, "</div>",
        f"<div class='nc-chips'>{''.join(chips)}</div>" if chips else "",
        task or (f"<div class='nc-note'>{e(note)}</div>" if note else ""),
    ])
    detail_html = "".join([
        f"<div class='nc-rows'>{body}</div>" if body else "",
        f"<div class='nc-foot'>{e(foot)}</div>" if foot else "",
        extra,
    ])
    if collapsible:
        return (f"<details class='card nc nc-fold'><summary>{head_html}<div class='nc-toggle'></div></summary>"
                f"{detail_html}</details>")
    return f"<div class='card nc'>{head_html}{detail_html}</div>"


def kpi_html(items) -> str:
    cells = "".join(f"<div class='nw-card'><div class='nw-title'>{e(t)}</div><div class='nw-value' style='color:{col};'>{e(v)}</div></div>" for t, v, col in items)
    return f"<div class='nw-grid'>{cells}</div>"


# --------------------------------------------------------------------------- « Nouvelles » : texte libre rangé par l'IA (Gemini)
APPEND_FIELDS = {"associations": ", ", "conseil": " · ", "anecdote": " · ", "raconte": " · ", "projets": " · ", "hobbies": ", ", "points_communs": ", ", "utile_pour": " · "}
REPLACE_FIELDS = ["ecole", "niveau", "etudes", "employeur", "fonction", "categorie", "relation", "tache", "echeance"]
NEWS_FIELDS = list(APPEND_FIELDS) + REPLACE_FIELDS
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]   # analyse : bon et pas cher
GEMINI_FAST = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]                        # dictée : le plus rapide


def news_prompt(text, contacts, today, event_date, selected=None):
    """selected : contacts choisis par Antoine dans l'app (la note parle d'eux). Sinon, l'IA cherche dans tout le réseau."""
    pool = selected or contacts
    roster = "\n".join(f"{c['id']} | {c.get('prenom', '')} {c.get('nom', '')} | {study_line(c) or '-'} | {job_line(c) or c.get('institution', '') or '-'}" for c in pool)
    cats = ", ".join(n for n, _ in CATEGORIES)
    who = ("Antoine a déjà choisi les personnes concernées (liste ci-dessous) : range les informations sur elles. "
           "Si la note parle clairement d'une autre personne absente de la liste, ajoute-la avec contact_id = null."
           if selected else
           "Repère chaque personne dont il parle et associe-la à un contact de la liste si c'est clairement elle.")
    return f"""Tu aides Antoine (étudiant en finance à Genève) à tenir son carnet de réseau. Il a écrit ou dicté une note
après une rencontre ou un événement de networking : ce que des personnes lui ont appris, dit ou proposé, et ce qu'il doit faire.
{who}

Date du jour : {today}. Date de la rencontre : {event_date}.

Contacts (id | prénom nom | études | emploi) :
{roster}

Champs possibles par personne (ne mets QUE ceux que la note renseigne vraiment) :
- conseil : conseil ou citation qu'il lui a donné, ce qu'il lui a appris
- anecdote : détail marquant, moment drôle, fait personnel
- raconte : sa personnalité, sa façon de fonctionner, comment Antoine s'entend avec lui, son parcours
- projets : ses projets d'avenir (études visées, poste rêvé, création d'entreprise, départ à l'étranger…)
- hobbies : sports et loisirs
- points_communs : ce qu'ils ont en commun
- utile_pour : la valeur ajoutée de cette personne dans le réseau d'Antoine (son expertise, son milieu, les portes qu'elle connaît)
- ecole : école ou faculté (GSEM, HEC Lausanne, LSE…), seulement si nouveau ou changé
- niveau : une de B1, B2, B3 (bachelor 1re à 3e année), « Bachelor obtenu » (bachelor fini, pas encore de master), M1, M2 (master), Doctorat — seulement si dit
- etudes : « En cours » ou « Terminées » — seulement si dit
- employeur : entreprise où il travaille (y compris stage ou temps partiel), seulement si nouveau ou changé
- associations : associations ou groupes où Antoine le côtoie (GUIC, Alumni GUIC, Comité GSEM, IFSA…), seulement si nouveau
- fonction : son poste chez cet employeur (Analyst, stage, temps partiel…), seulement si nouveau ou changé
- categorie : une de : {cats} (seulement si évident et nouveau)
- relation : Network, Ami ou À contacter (seulement si Antoine le dit)
- tache : seulement une action CONCRÈTE d'Antoine avec un délai PRÉCIS (date, « mi-novembre », « avant vendredi », « dans 2 semaines », « après ses examens en janvier »). Une simple intention ou attitude sans délai (« faudrait lui parler à l'occasion », « garder le contact », « le recroiser », « rester en lien ») n'est PAS une tâche : mets-la dans raconte sous la forme « À garder en tête : … »
- echeance : date AAAA-MM-JJ de cette action (obligatoire si tache) ; « mi-novembre » = le 15, « fin novembre » = le 30, « dans 2 semaines » à partir de la date du jour

Règles :
- La note peut être le récit oral d'une soirée entière qui parle de plusieurs personnes : une entrée par personne, sans mélanger leurs informations, chacune avec sa propre tâche si Antoine en mentionne une.
- Reformule proprement en français, phrases courtes, style notes. N'invente rien, ne déduis rien qui n'est pas écrit.
- Si plusieurs contacts peuvent correspondre, contact_id = null, ids possibles dans candidats, une phrase dans doute.
- historique : UNE phrase courte résumant l'échange (sans la date). Pas un fourre-tout : n'y recopie jamais ce qui est déjà rangé ailleurs.

À quoi servent ces notes (concentre-toi là-dessus, reste bref) :
1. Ajouter la nouveauté au BON endroit du profil : ce qu'il a dit ou conseillé -> conseil ; ses projets -> projets ; son caractère ou parcours -> raconte ;
   un détail marquant -> anecdote ; son milieu ou ses contacts -> utile_pour.
2. Noter un point commun ou un centre d'intérêt partagé -> points_communs (et hobbies pour ses loisirs).
3. Créer la TÂCHE : une action concrète d'Antoine (envoyer mon CV, relancer, café, appeler…) AVEC un délai précis -> tache + echeance.
   Sans délai précis, ce n'est pas une tâche : « À garder en tête : … » dans raconte.
Ne remplis école, niveau, employeur, fonction, associations, categorie, relation QUE si la note dit clairement que c'est nouveau ou changé.
Plusieurs phrases sur une personne = plusieurs champs remplis (tâche et nouveauté), pas seulement l'historique.
Noms : à l'oral, un nom est souvent mal entendu. S'il ressemble (même phonétiquement) à un contact de la liste, choisis ce contact au lieu d'en créer un nouveau.

Réponds UNIQUEMENT en JSON, de la forme :
{{"evenement": "", "personnes": [{{"contact_id": "id ou null", "candidats": [], "doute": "", "prenom": "", "nom": "",
  "historique": "", "champs": {{"conseil": "", "tache": "", "echeance": ""}}}}]}}

Note d'Antoine :
\"\"\"{text}\"\"\""""


class _GemFatal(Exception):
    pass


def _gemini_once(m, parts, api_key, json_mode, timeout, think):
    """Un appel à UN modèle. Renvoie le texte ou lève une erreur (courte)."""
    import requests
    cfg = {"temperature": 0.2}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
    for use_think in (True, False):
        c = dict(cfg)
        if use_think and think:
            c["thinkingConfig"] = ({"thinkingBudget": 0 if think == "minimal" else 1024} if "2.5" in m else {"thinkingLevel": think})
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": c}
        try:
            r = requests.post(url, params={"key": api_key}, json=body, timeout=timeout)
        except requests.RequestException as ex:
            raise RuntimeError(type(ex).__name__)
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (KeyError, IndexError, ValueError):
                raise RuntimeError("réponse vide")
        if r.status_code == 400 and use_think and "think" in r.text.lower():
            continue                                   # réglage refusé par ce modèle : on refait sans
        if r.status_code in (401, 403):
            raise _GemFatal(f"Clé Gemini refusée ({r.status_code}) : vérifie GEMINI_API_KEY et le crédit du projet.")
        if r.status_code in (400, 404) and "not found" in r.text.lower():
            raise RuntimeError("modèle introuvable")
        raise RuntimeError({503: "surchargé", 429: "quota atteint"}.get(r.status_code, f"erreur {r.status_code} {r.text[:100]!r}"))
    raise RuntimeError("réglage refusé")


def gemini_generate(parts, api_key, model=None, json_mode=True, timeout=20, models=None, retries=0, think="minimal",
                    parallel=2, hedge=6.0, deadline=28.0):
    """Appelle Gemini et renvoie (texte, modèle utilisé).
    Course entre modèles : les `parallel` premiers partent en même temps, le suivant part après `hedge` secondes
    (ou tout de suite si un modèle échoue). La première bonne réponse gagne. Limite totale : `deadline` secondes."""
    import time
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    order = ([model] if model else []) + [m for m in (models or GEMINI_MODELS) if m != model]
    start = time.time()
    ex = ThreadPoolExecutor(max_workers=len(order))
    pending, errors, idx = {}, [], 0

    def launch():
        nonlocal idx
        f = ex.submit(_gemini_once, order[idx], parts, api_key, json_mode, timeout, think)
        pending[f] = order[idx]
        idx += 1

    try:
        while idx < min(parallel, len(order)):
            launch()
        next_at = start + hedge
        while pending or idx < len(order):
            now = time.time()
            if now - start >= deadline:
                errors.append(f"trop lent (> {deadline:.0f} s)")
                break
            if not pending:
                launch()
                next_at = time.time() + hedge
                continue
            limit = start + deadline - now
            if idx < len(order):
                limit = min(limit, max(0.05, next_at - now))
            done, _ = wait(list(pending), timeout=max(0.05, limit), return_when=FIRST_COMPLETED)
            for f in done:
                m = pending.pop(f)
                try:
                    return f.result(), m
                except _GemFatal as e:
                    raise RuntimeError(str(e))
                except Exception as e:
                    errors.append(f"{m} : {e}")
                    if idx < len(order):
                        launch()                        # un échec : on lance tout de suite le suivant
                        next_at = time.time() + hedge
            if not done and idx < len(order) and time.time() >= next_at:
                launch()
                next_at = time.time() + hedge
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    raise RuntimeError("Gemini indisponible pour le moment (" + " ; ".join(errors) + "). Réessaie dans une minute.")


def gemini_json(prompt, api_key, model=None, timeout=20, deadline=28.0, think="minimal"):
    """Texte -> objet JSON (course entre deux modèles, limite de temps stricte)."""
    txt, m = gemini_generate([{"text": prompt}], api_key, model, json_mode=True, timeout=timeout, deadline=deadline, think=think)
    if txt.startswith("```"):
        txt = re.sub(r"^```(json)?|```$", "", txt).strip()
    try:
        return json.loads(txt), m
    except ValueError:
        raise RuntimeError(f"Réponse de Gemini illisible ({m}). Réessaie.")


AUDIO_NOTE = "\n[Un enregistrement audio est joint : écoute-le, il fait partie de la note.]"
AUDIO_NOTE_TEXT = " Ajoute au JSON la clé \"transcription\" : sa transcription fidèle, ponctuée."
GEMINI_DIRECT = ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.1-flash-lite"]   # écoute + analyse : qualité d'abord


def gemini_audio_json(prompt, audio: bytes, mime: str, api_key, model=None, timeout=60, transcript=False):
    """Dictée + analyse en UN seul appel : le modèle écoute l'audio et renvoie le JSON (avec la clé « transcription »)."""
    import base64
    note = AUDIO_NOTE[:-1] + AUDIO_NOTE_TEXT + "]" if transcript else AUDIO_NOTE
    parts = [{"text": prompt + note}, {"inline_data": {"mime_type": mime or "audio/wav", "data": base64.b64encode(audio).decode()}}]
    txt, m = gemini_generate(parts, api_key, model, json_mode=True, timeout=timeout, models=GEMINI_DIRECT, think="minimal", deadline=35.0)
    if txt.startswith("```"):
        txt = re.sub(r"^```(json)?|```$", "", txt).strip()
    try:
        obj = json.loads(txt)
    except ValueError:
        raise RuntimeError(f"Réponse de Gemini illisible ({m}).")
    if not isinstance(obj, dict):
        raise RuntimeError("Réponse de Gemini inattendue.")
    return obj, m


LAST = {}


def transcribe(audio: bytes, mime: str, api_key, model=None) -> str:
    """Dictée : message vocal -> texte français fidèle (ponctué), via Gemini."""
    import base64
    parts = [{"text": "Transcris fidèlement ce message vocal, en français, avec la ponctuation. "
                      "Réponds uniquement avec le texte transcrit, sans commentaire."},
             {"inline_data": {"mime_type": mime or "audio/wav", "data": base64.b64encode(audio).decode()}}]
    txt, _m = gemini_generate(parts, api_key, model, json_mode=False, timeout=15, models=GEMINI_FAST, parallel=1, hedge=5.0, deadline=20.0)
    LAST["dictee"] = _m
    return txt.strip().strip('"')


def clean_proposal(res, contacts):
    """Normalise la réponse de l'IA : ids valides, champs connus, dates ISO."""
    ids = {c["id"] for c in contacts}
    out = []
    for p in (res or {}).get("personnes", []) or []:
        cid = p.get("contact_id") or None
        if cid not in ids:
            cid = None
        cands = [x for x in (p.get("candidats") or []) if x in ids]
        champs = {}
        for k, v in (p.get("champs") or {}).items():
            if k in NEWS_FIELDS and v not in (None, ""):
                v = str(v).strip()
                if k == "echeance":
                    d = parse_date(v)
                    if not d:
                        continue
                    v = d.isoformat()
                if k == "relation" and v not in RELATIONS:
                    continue
                if k == "niveau" and v not in NIVEAUX:
                    continue
                if k == "etudes" and v not in ETUDES:
                    continue
                if k == "categorie" and v not in CAT_ICON:
                    continue
                champs[k] = v
        out.append(dict(contact_id=cid, candidats=cands, doute=str(p.get("doute") or ""), prenom=str(p.get("prenom") or ""),
                        nom=str(p.get("nom") or ""), historique=str(p.get("historique") or ""), champs=task_guard(champs)))
    return out


def task_guard(champs: dict) -> dict:
    """Une tâche n'est gardée que si elle a une échéance précise. Sinon c'est une intention : elle va dans « raconte »."""
    t = str(champs.get("tache") or "").strip()
    if t and not champs.get("echeance"):
        champs.pop("tache", None)
        note = "À garder en tête : " + t[0].lower() + t[1:] if not t.lower().startswith("à garder") else t
        champs["raconte"] = (champs["raconte"] + " · " + note) if champs.get("raconte") else note
    elif champs.get("echeance") and not t:
        champs.pop("echeance", None)
    return champs


def news_changes(c, champs, hist_line, event_date):
    """Changements à enregistrer sur un contact existant : ajout à la suite pour les textes, remplacement pour le reste."""
    ch = {}
    for k, v in champs.items():
        v = (v or "").strip()
        if not v:
            continue
        if k in APPEND_FIELDS:
            cur = (c.get(k) or "").strip()
            if v in cur:
                continue
            ch[k] = (cur + APPEND_FIELDS[k] + v) if cur else v
        else:
            ch[k] = v
    if hist_line.strip():
        cur = (c.get("historique") or "").strip()
        ch["historique"] = (cur + "\n" if cur else "") + hist_line.strip()
    d = parse_date(event_date)
    last = parse_date(c.get("dernier_contact"))
    if d and (not last or d > last):
        ch["dernier_contact"] = d.isoformat()
    return ch


def hist_line(event_date, event_name, text):
    d = parse_date(event_date).strftime("%d.%m.%Y") if parse_date(event_date) else ""
    head = " · ".join(x for x in (d, (event_name or "").strip()) if x)
    return f"{head} : {text.strip()}" if head and text.strip() else (text.strip() or "")


# --------------------------------------------------------------------------- photos
def make_thumb(data: bytes, size: int = 160) -> str:
    """Photo -> carré recadré au centre, JPEG léger, en base64 (≈ 6–12 ko, tient dans une cellule Google Sheet)."""
    import base64
    import io
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, max(0, (h - s) // 3), (w - s) // 2 + s, max(0, (h - s) // 3) + s)).resize((size, size), Image.LANCZOS)
    for q in (82, 70, 55):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if len(b64) < 40000:
            return b64
    return b64


def event_view(contacts, assocs, today: date | None = None):
    """Préparer un événement : les contacts des associations choisies, ceux avec une tâche d'abord (retard, puis échéance)."""
    today = today or date.today()
    people = search(contacts, "", None, None, None, assocs)
    with_task = [c for c in people if c.get("tache") or c.get("echeance")]
    others = [c for c in people if c not in with_task]
    with_task.sort(key=lambda c: (parse_date(c.get("echeance")) or date.max, norm(c.get("prenom", ""))))
    others.sort(key=lambda c: (last_touch(c) or date.min, norm(c.get("prenom", ""))))      # les moins revus d'abord
    late = sum(1 for c in with_task if (parse_date(c.get("echeance")) or date.max) < today)
    return with_task, others, late


# --------------------------------------------------------------------------- « Ajouter » : description libre -> champs pré-remplis
CONTACT_AI_FIELDS = ["prenom", "nom", "rencontre_ou", "raconte", "projets", "hobbies", "points_communs", "conseil", "anecdote", "utile_pour",
                     "relation", "categorie", "ecole", "niveau", "etudes", "employeur", "fonction", "associations", "tache", "echeance", "linkedin"]


def contact_prompt(text, today, known: dict):
    cats = ", ".join(n for n, _ in CATEGORIES)
    have = "; ".join(f"{LABELS.get(k, k)} = {v}" for k, v in known.items() if v) or "rien"
    return f"""Tu aides Antoine (étudiant en finance à Genève, membre du GUIC) à noter une nouvelle rencontre de networking.
Il décrit la personne librement (souvent dicté). Remplis les champs ci-dessous à partir de sa description.
Date du jour : {today}. Déjà saisi par Antoine (ne le contredis pas) : {have}.

Champs (ne mets QUE ce que la description dit vraiment, chaîne vide sinon) :
- prenom, nom : prénom et nom de famille de la personne (orthographe la plus probable)
- rencontre_ou : où ou dans quel cadre ils se sont rencontrés (« Soirée GUIC », « Coffee chat », « Uniparty »…)
- raconte : sa personnalité, sa façon de fonctionner, comment Antoine s'entend avec lui, son parcours
- projets : ses projets d'avenir (études visées, poste rêvé, création d'entreprise, départ à l'étranger…)
- hobbies : sports et loisirs
- points_communs : ce qu'ils ont en commun
- conseil : conseil ou citation qu'il a donné à Antoine
- anecdote : détail marquant, moment drôle
- utile_pour : sa valeur ajoutée dans le réseau d'Antoine (expertise, milieu, portes qu'il connaît)
- relation : Network, Ami ou À contacter (seulement si c'est clair)
- categorie : une de : {cats}
- ecole : école ou faculté ; niveau : B1, B2, B3, Bachelor obtenu, M1, M2 ou Doctorat ; etudes : En cours ou Terminées
- employeur : entreprise où il travaille (y compris stage) ; fonction : son poste
- associations : GUIC, Alumni GUIC, Comité GSEM, IFSA ou autre association citée (séparées par des virgules)
- tache : seulement une action CONCRÈTE d'Antoine avec un délai PRÉCIS (date, « mi-novembre », « avant vendredi », « dans 2 semaines », « après ses examens en janvier »). Une simple intention ou attitude sans délai (« faudrait lui parler à l'occasion », « garder le contact », « le recroiser », « rester en lien ») n'est PAS une tâche : mets-la dans raconte sous la forme « À garder en tête : … » ; echeance : date AAAA-MM-JJ, obligatoire si tache (« mi-novembre » = le 15, « fin novembre » = le 30)

Règles : français, phrases courtes style notes, reformule proprement, n'invente rien.
Réponds UNIQUEMENT en JSON : {{"champs": {{"rencontre_ou": "", "raconte": "", "...": ""}}}}

Description d'Antoine :
\"\"\"{text}\"\"\""""


def clean_contact_fields(res) -> dict:
    out = {}
    for k, v in ((res or {}).get("champs") or {}).items():
        if k not in CONTACT_AI_FIELDS or v in (None, ""):
            continue
        v = str(v).strip()
        if k == "echeance":
            d = parse_date(v)
            if not d:
                continue
            v = d.isoformat()
        if k == "linkedin":
            if "linkedin.com/in/" not in v.lower():
                continue
            v = v if v.lower().startswith("http") else "https://" + v.lstrip("/")
        if (k == "relation" and v not in RELATIONS) or (k == "categorie" and v not in CAT_ICON) \
                or (k == "niveau" and v not in NIVEAUX) or (k == "etudes" and v not in ETUDES):
            continue
        out[k] = v
    return task_guard(out)


# --------------------------------------------------------------------------- import d'un profil LinkedIn (PDF « Enregistrer au format PDF » ou texte)
def profile_text(data: bytes, name: str) -> str:
    """Texte d'un profil : PDF lu localement (pypdf), sinon .md / .txt. '' si illisible."""
    if name.lower().endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:6]).strip()
        except Exception:
            return ""
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc).strip()
        except UnicodeDecodeError:
            pass
    return ""


EDU_HEAD = re.compile(r"^\s*(Formation|Education|Études|Etudes|Ausbildung)\s*$", re.I | re.M)
EDU_END = re.compile(r"^\s*(Licences et certifications|Licenses? (&|and) certifications?|Certifications?|Bénévolat|Volunteer.*|Compétences|Skills|"
                     r"Langues|Languages|Distinctions.*|Honors.*|Publications|Projets|Projects|Recommandations|Recommendations|Centres d'intérêt|Interests|Page \d+.*)\s*$", re.I | re.M)


def education_block(text: str) -> str:
    """Section « Formation » du profil, recopiée telle quelle (pour que l'IA s'y concentre)."""
    m = EDU_HEAD.search(text or "")
    if not m:
        return ""
    rest = text[m.end():]
    e = EDU_END.search(rest)
    return rest[: e.start() if e else 2500].strip()[:2500]


def linkedin_prompt(text, today):
    cats = ", ".join(n for n, _ in CATEGORIES)
    edu = education_block(text)
    edu_txt = f"\nSection « Formation » repérée dans le profil (à analyser en priorité pour les études) :\n\"\"\"{edu}\"\"\"\n" if edu else ""
    return f"""Voici le texte d'un profil LinkedIn (export PDF ou copie). Antoine (étudiant en finance à Genève) veut l'ajouter à son carnet de réseau.
Date du jour : {today}. Extrais l'essentiel, en français, style notes, sans rien inventer.

Champs :
- prenom, nom
- employeur : l'entreprise du poste ACTUEL (celui sans date de fin, « aujourd'hui », « Present »). Un stage en cours compte.
- fonction : intitulé du poste actuel, suivi de « · depuis MM.AAAA » si la date de début est donnée (ex. « Analyst · depuis 03.2024 »)
- raconte : 2 à 4 points courts séparés par « · » : ce qu'il fait dans son poste actuel (tâches, équipe), où il est basé (ville),
  puis son parcours précédent en bref (postes et entreprises, du plus récent au plus ancien)
- ecole, niveau, etudes : voir « Études » ci-dessous
- utile_pour : son expertise ou son milieu, utile pour le réseau d'Antoine (une phrase) ; ajoute à la fin « Certifications : … » s'il en a
  (CFA, CAIA, FRM, CAS, DAS, cours en ligne…)
- categorie : une de : {cats}
- associations : associations ou organisations étudiantes citées (GUIC, IFSA…), sinon rien
- linkedin : l'adresse du profil si elle apparaît (linkedin.com/in/…)

Études (important, lis toute la section Formation, ligne par ligne) :
1. Ne garde QUE les cursus universitaires diplômants : Bachelor (BSc, BA, Licence), Master (MSc, MA, MBA à plein temps), Doctorat (PhD),
   dans une université ou une haute école (UNIGE, HEC Lausanne, EPFL, HSG, HEG, LSE, ESSEC…).
2. IGNORE pour ces champs la formation continue et les certificats : CAS, DAS, MAS, Executive / Exec Ed, certificat, diplôme de langue,
   CFA / CAIA / FRM, cours en ligne (Coursera, edX, Udemy, LinkedIn Learning), bootcamps, séjours d'échange, maturité / bac / lycée.
3. ecole = l'établissement du cursus universitaire le plus élevé, ou de celui en cours s'il y en a un (avec la faculté si elle est écrite, ex. « UNIGE – GSEM »).
4. etudes = « En cours » si la date de fin de ce cursus est après {today} ou absente avec « aujourd'hui » ; sinon « Terminées ».
5. niveau :
   - Master en cours : M1 si commencé il y a moins d'un an, sinon M2 ; Master terminé : M2.
   - Bachelor en cours (sans master) : B1, B2 ou B3 selon l'année depuis le début ; Bachelor terminé sans master : « Bachelor obtenu ».
   - Doctorat (en cours ou terminé) : Doctorat.
   - Si les dates manquent et que ce n'est pas clair : laisse vide.
{edu_txt}
Réponds UNIQUEMENT en JSON : {{"champs": {{"prenom": "", "nom": "", "employeur": "", "fonction": "", "raconte": "", "ecole": "", "niveau": "", "etudes": "", "...": ""}}}}

Profil complet :
\"\"\"{text[:12000]}\"\"\"
"""


def gemini_pdf_json(prompt, data: bytes, api_key, model=None):
    """PDF illisible localement (scan) : on l'envoie tel quel à Gemini."""
    import base64
    parts = [{"text": prompt}, {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(data).decode()}}]
    txt, m = gemini_generate(parts, api_key, model, json_mode=True, timeout=30, deadline=40.0)
    if txt.startswith("```"):
        txt = re.sub(r"^```(json)?|```$", "", txt).strip()
    try:
        return json.loads(txt), m
    except ValueError:
        raise RuntimeError(f"Réponse de Gemini illisible ({m}).")
