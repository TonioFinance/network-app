"""Logique de l'app Network (sans Streamlit) : colonnes, stockage Google Sheet ou CSV local, relances, cartes HTML.

Le Google Sheet a un onglet « Contacts » dont la ligne 1 contient les identifiants de COLUMNS.
Il est créé automatiquement au premier lancement.
"""
from __future__ import annotations

import csv
import html
import re
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------- colonnes du Google Sheet
COLUMNS = [
    "id", "cree_le", "prenom", "nom", "categorie", "institution", "poste", "rencontre_ou", "date_rencontre",
    "anecdote", "raconte", "hobbies", "points_communs", "utile_pour", "chaleur", "tache", "echeance",
    "dernier_contact", "telephone", "linkedin", "importe", "relation", "conseil",
]
LABELS = {
    "prenom": "Prénom", "nom": "Nom", "categorie": "Catégorie", "institution": "Institution / école",
    "poste": "Poste ou filière", "rencontre_ou": "Rencontré où", "date_rencontre": "Date de la rencontre",
    "anecdote": "Anecdote / phrase marquante", "raconte": "Ce qu'il m'a raconté", "hobbies": "Sport, hobbies",
    "points_communs": "Points communs", "utile_pour": "Utile pour…", "chaleur": "Chaleur du contact",
    "tache": "Tâche à faire", "echeance": "Échéance", "dernier_contact": "Dernier contact",
    "telephone": "Numéro", "linkedin": "Lien LinkedIn", "relation": "Relation",
    "conseil": "Conseil qu'il m'a donné",
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


class SheetStore:
    """Google Sheet (gspread). Onglet « Contacts », ligne 1 = COLUMNS. Les colonnes manquantes sont ajoutées à droite."""

    def __init__(self, gc, sheet_id: str, tab: str = "Contacts"):
        sh = gc.open_by_key(sheet_id)
        try:
            self.ws = sh.worksheet(tab)
        except Exception:
            self.ws = sh.add_worksheet(title=tab, rows=500, cols=len(COLUMNS))
            self.ws.update(range_name="A1", values=[COLUMNS])
        head = self.ws.row_values(1)
        if not head:
            self.ws.update(range_name="A1", values=[COLUMNS])
            head = list(COLUMNS)
        missing = [c for c in COLUMNS if c not in head]
        if missing:
            head = head + missing
            if self.ws.col_count < len(head):
                self.ws.add_cols(len(head) - self.ws.col_count)
            self.ws.update(range_name="A1", values=[head])
        self.head = head

    def all(self) -> list[dict]:
        vals = self.ws.get_all_values()
        if not vals:
            return []
        head = vals[0]
        out = []
        for row in vals[1:]:
            r = {h: (row[i] if i < len(row) else "") for i, h in enumerate(head)}
            if r.get("id"):
                out.append({k: r.get(k, "") for k in COLUMNS})
        return out

    def add(self, c: dict):
        self.ws.append_row([c.get(h, "") for h in self.head], value_input_option="RAW")

    def _row_of(self, cid: str) -> int | None:
        ids = self.ws.col_values(self.head.index("id") + 1)
        return ids.index(cid) + 1 if cid in ids else None

    def update(self, cid: str, changes: dict):
        r = self._row_of(cid)
        if not r:
            raise KeyError(cid)
        cur = self.ws.row_values(r)
        cur += [""] * (len(self.head) - len(cur))
        for k, v in changes.items():
            if k in self.head and k != "id":
                cur[self.head.index(k)] = "" if v is None else str(v)
        self.ws.update(range_name=f"A{r}", values=[cur], value_input_option="RAW")

    def delete(self, cid: str):
        r = self._row_of(cid)
        if r:
            self.ws.delete_rows(r)


# --------------------------------------------------------------------------- recherche et relances
def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


SEARCH_FIELDS = ["prenom", "nom", "institution", "poste", "categorie", "rencontre_ou", "anecdote", "conseil", "raconte",
                 "hobbies", "points_communs", "utile_pour", "tache"]


def inst_tokens(s) -> list:
    """« GSEM / UBS » -> ['GSEM', 'UBS'] : une institution par morceau (séparateurs / , ; + & ·)."""
    out = []
    for part in re.split(r"[/,;+&·]|\bet\b", str(s or "")):
        part = part.strip()
        if part:
            out.append(part)
    return out


def institutions(contacts) -> list:
    """Liste (nom affiché, nombre de contacts), la plus fournie d'abord. Les variantes de casse sont regroupées."""
    count, label = {}, {}
    for c in contacts:
        for t in {norm(x).strip(): x for x in inst_tokens(c.get("institution"))}.items():
            count[t[0]] = count.get(t[0], 0) + 1
            label.setdefault(t[0], t[1])
    return sorted(((label[k], n) for k, n in count.items()), key=lambda x: (-x[1], norm(x[0])))


def search(contacts, q="", cats=None, insts=None, relations=None):
    words = norm(q).split()
    out = []
    for c in contacts:
        if cats and c["categorie"] not in cats:
            continue
        if insts:
            mine = {norm(x).strip() for x in inst_tokens(c.get("institution"))}
            if not mine & {norm(i).strip() for i in insts}:
                continue
        if relations and c.get("relation", "") not in relations:
            continue
        blob = norm(" ".join(c.get(k, "") for k in SEARCH_FIELDS))
        if all(w in blob for w in words):
            out.append(c)
    return sorted(out, key=lambda c: (c.get("dernier_contact") or c.get("date_rencontre") or c.get("cree_le") or ""), reverse=True)


def last_touch(c) -> date | None:
    return parse_date(c.get("dernier_contact")) or parse_date(c.get("date_rencontre")) or parse_date((c.get("cree_le") or "")[:10])


def relances(contacts, today: date | None = None):
    """Trois listes : en retard (échéance passée), cette semaine (échéance dans les 7 jours), sans nouvelles."""
    today = today or date.today()
    late, week, silent = [], [], []
    for c in contacts:
        ech = parse_date(c.get("echeance"))
        if c.get("tache") or ech:
            if ech and ech < today:
                late.append(c)
            elif ech and ech <= today + timedelta(days=7):
                week.append(c)
            elif not ech and c.get("tache"):
                week.append(c)
            continue
        lt = last_touch(c)
        if c.get("chaleur") in ("Chaud", "Tiède") and lt and (today - lt).days >= SANS_NOUVELLES_JOURS:
            silent.append(c)
    late.sort(key=lambda c: c["echeance"])
    week.sort(key=lambda c: c["echeance"] or "9999")
    silent.sort(key=lambda c: last_touch(c) or date.min)
    return late, week, silent


def duplicates(contacts, prenom, nom):
    p, n = norm(prenom).strip(), norm(nom).strip()
    return [c for c in contacts if norm(c["prenom"]).strip() == p and norm(c["nom"]).strip() == n]


# --------------------------------------------------------------------------- HTML (aucune indentation en début de ligne : Markdown)
def e(s) -> str:
    return html.escape(str(s or ""))


def initials(c) -> str:
    return ((c.get("prenom") or "?")[:1] + (c.get("nom") or "")[:1]).upper()


def contact_card_html(c, today: date | None = None, extra="") -> str:
    today = today or date.today()
    icon = CAT_ICON.get(c.get("categorie"), "ph-user")
    sub = " · ".join(x for x in (c.get("institution"), c.get("poste")) if x)
    chips = []
    if c.get("categorie"):
        chips.append(f"<span class='chip'><i class='ph {icon}'></i> {e(c['categorie'])}</span>")
    if c.get("relation"):
        chips.append(f"<span class='chip'><i class='ph ph-tag'></i> {e(c['relation'])}</span>")
    met = " · ".join(x for x in (c.get("rencontre_ou"), fr_date(c.get("date_rencontre"))) if x)
    lines = []
    if c.get("anecdote"):
        lines.append(f"<div class='nc-quote'><i class='ph ph-quotes'></i> {e(c['anecdote'])}</div>")
    facts = [("ph-lightbulb", c.get("conseil")), ("ph-chat-circle-text", c.get("raconte")), ("ph-person-simple-run", c.get("hobbies")),
             ("ph-link-simple", c.get("points_communs")), ("ph-target", c.get("utile_pour"))]
    for ic, v in facts:
        if v:
            lines.append(f"<div class='nc-fact'><i class='ph {ic}'></i><span>{e(v)}</span></div>")
    task = ""
    if c.get("tache") or c.get("echeance"):
        ech = parse_date(c.get("echeance"))
        cls = "late" if ech and ech < today else ""
        when = f" · {fr_date(ech)}" if ech else ""
        task = f"<div class='nc-task {cls}'><i class='ph ph-check-square'></i> {e(c.get('tache') or 'À faire')}{e(when)}</div>"
    lt = last_touch(c)
    foot = f"Dernier contact : {fr_date(lt)}" if lt else ""
    li = ""
    if c.get("linkedin"):
        li = f"<a class='nc-li' href='{e(c['linkedin'])}' target='_blank' rel='noopener'><i class='ph ph-linkedin-logo'></i></a>"
    return "".join([
        "<div class='card nc'>",
        "<div class='nc-head'>",
        f"<div class='nc-avatar'>{e(initials(c))}</div>",
        "<div class='nc-id'>",
        f"<div class='nc-name'>{e(c.get('prenom'))} <b>{e((c.get('nom') or '').upper())}</b></div>",
        f"<div class='nc-sub'>{e(sub)}</div>" if sub else "",
        "</div>", li, "</div>",
        f"<div class='nc-chips'>{''.join(chips)}</div>" if chips else "",
        f"<div class='nc-met'><i class='ph ph-map-pin'></i> {e(met)}</div>" if met else "",
        "".join(lines), task,
        f"<div class='nc-foot'>{e(foot)}</div>" if foot else "",
        extra,
        "</div>",
    ])


def kpi_html(items) -> str:
    cells = "".join(f"<div class='nw-card'><div class='nw-title'>{e(t)}</div><div class='nw-value' style='color:{col};'>{e(v)}</div></div>" for t, v, col in items)
    return f"<div class='nw-grid'>{cells}</div>"
