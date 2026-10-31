#!/usr/bin/env python3
"""Synchronise l'Excel (onglet « Network ») et l'app Network (Google Sheet). L'EXCEL PRÉVAUT.

    python3 importer_network.py                  # synchronise (c'est aussi ce que fait l'automatisation de 21h30)
    python3 importer_network.py --simulation     # montre ce qui serait fait, sans rien écrire
    python3 importer_network.py --sauvegarde     # synchronise et force une copie de secours du Google Sheet
    python3 importer_network.py --csv export.csv # ajoute à l'Excel les contacts d'un CSV (sans Google)

Le Google Sheet a deux onglets :
- « Saisies » : tout ce que tu saisis dans l'app (ajouts, modifications), avec un statut. Jamais réécrit.
- « Réseau » : la copie de l'Excel. L'app affiche cet onglet.

La synchro :
1. reporte dans l'Excel les saisies « à synchroniser » du journal, dans l'ordre :
   - ajout : nouveau contact écrit en bleu sous les autres (ignoré si même ID ou même prénom et nom) ;
   - modification : chaque champ est écrit en bleu dans l'Excel SI la cellule de l'Excel n'a pas changé entre-temps ;
     sinon l'Excel gagne et le champ est marqué « ignoré » dans le journal ;
2. donne un ID app aux contacts de l'Excel qui n'en ont pas (colonne Q masquée) ;
3. recopie tout l'onglet Network de l'Excel dans l'onglet « Réseau » (ce qui a été supprimé ou corrigé dans l'Excel
   disparaît ou est corrigé dans l'app) ;
4. écrit le résultat de chaque saisie dans la colonne « statut » du journal.
Avant toute écriture, l'Excel d'avant est copié dans « 3. Suivi - Archives/JJ.MM.AAAA_HHhMM/ » avec un Suivi.md.
Une fois par semaine, copie de secours des deux onglets dans « 3. Suivi - Archives/Sauvegardes Network/ ».
L'Excel doit être fermé. Le fichier est modifié directement en XML : listes déroulantes et mises en forme intactes.

Connexion Google : .streamlit/secrets.toml (comme l'app) ou cle_google.json, dans le dossier du script.
Il faut : pip3 install gspread google-auth tomli
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import network_core as nc  # noqa: E402

XLSX_DEFAULT = HERE.parent / "Suivi_Recherche_Emploi.xlsx"
ARCHIVES_NAME = "3. Suivi - Archives"
SHEET_NAME = "Network"
FIRST_ROW = 6
BLUE = "FF1F4FD8"

# colonnes ajoutées à droite de « Dernier contact » : (lettre, titre, largeur, type de style)
EXTRA = [
    ("J", "Catégorie", 22, "text"), ("K", "Poste / études", 22, "text"), ("L", "Rencontré (où, quand)", 24, "text"),
    ("M", "Anecdote", 40, "long"), ("N", "Sport / hobbies", 22, "text"), ("O", "Points communs", 26, "text"),
    ("P", "Conseil donné", 40, "long"), ("Q", "ID app", 12, "text"), ("R", "Relation", 14, "text"),
    ("S", "Historique", 50, "long"), ("T", "Projets d'avenir", 40, "long"),
    ("U", "École / faculté", 20, "text"), ("V", "Niveau d'études", 10, "text"), ("W", "Études", 11, "text"),
    ("X", "Employeur", 24, "text"), ("Y", "Poste", 26, "text"), ("Z", "Associations", 24, "text"),
]
NIVEAUX = ["B1", "B2", "B3", "Bachelor obtenu", "M1", "M2", "Doctorat"]
ETUDES = ["En cours", "Terminées"]
RELATIONS = ["Network", "Ami", "À contacter"]
ID_COL = "Q"
LAST_COL = "Z"


# --------------------------------------------------------------------------- outils XML
def col_num(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def split_ref(ref: str):
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    return m.group(1), int(m.group(2))


CELL_RE = re.compile(r'<c r="([A-Z]+)(\d+)"[^>]*?(?:/>|>.*?</c>)', re.S)


def serial(d: date) -> int:
    return (d - date(1899, 12, 30)).days


def from_serial(v) -> date | None:
    try:
        return date.fromordinal(date(1899, 12, 30).toordinal() + int(float(v)))
    except (TypeError, ValueError):
        return None


class Book:
    """Classeur ouvert en mémoire (fichiers du zip), avec juste ce qu'il faut pour l'onglet Network."""

    def __init__(self, path: Path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.names = z.namelist()
            self.files = {n: z.read(n) for n in self.names}
        wb = self.txt("xl/workbook.xml")
        sheets = re.findall(r'<sheet [^>]*?name="([^"]+)"[^>]*?r:id="([^"]+)"', wb)
        names = [n.replace("&amp;", "&") for n, _ in sheets]
        if SHEET_NAME not in names:
            raise SystemExit(f"Onglet « {SHEET_NAME} » introuvable dans {path.name}.")
        self.sheet_index = names.index(SHEET_NAME)
        rid = sheets[self.sheet_index][1]
        rels = self.txt("xl/_rels/workbook.xml.rels")
        target = re.search(r'<Relationship [^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or re.search(r'<Relationship [^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
        t = target.group(1).lstrip("/")
        self.sheet_path = t if t.startswith("xl/") else "xl/" + t
        self.rels_path = self.sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
        self.sheet = self.txt(self.sheet_path)
        sst = self.txt("xl/sharedStrings.xml") if "xl/sharedStrings.xml" in self.files else ""
        self.sst = [self._si_text(si) for si in re.findall(r"<si>(.*?)</si>", sst, re.S)]
        self.styles = self.txt("xl/styles.xml")
        self.blue_cache = {}

    def txt(self, name):
        return self.files[name].decode("utf8")

    @staticmethod
    def _si_text(si):
        return "".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")

    # ---- lecture
    def rows(self):
        return {int(m.group(1)): m.group(0) for m in re.finditer(r'<row r="(\d+)"[^>]*?(?:/>|>.*?</row>)', self.sheet, re.S)}

    def cells(self, row_xml):
        return {m.group(1): m.group(0) for m in CELL_RE.finditer(row_xml)}

    def value(self, cell_xml):
        if cell_xml is None:
            return ""
        t = re.search(r'\bt="([^"]+)"', cell_xml.split(">", 1)[0])
        t = t.group(1) if t else ""
        if t == "inlineStr":
            return self._si_text(cell_xml)
        v = re.search(r"<v>(.*?)</v>", cell_xml, re.S)
        if not v:
            return ""
        v = v.group(1)
        if t == "s":
            return self.sst[int(v)]
        return v.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    def style(self, cell_xml):
        m = re.search(r'\bs="(\d+)"', cell_xml.split(">", 1)[0]) if cell_xml else None
        return m.group(1) if m else "0"

    def hyperlinks(self):
        rels = self.txt(self.rels_path) if self.rels_path in self.files else ""
        tg = dict(re.findall(r'<Relationship [^>]*?Id="([^"]+)"[^>]*?Target="([^"]+)"', rels))
        tg.update({b: a for a, b in re.findall(r'<Relationship [^>]*?Target="([^"]+)"[^>]*?Id="([^"]+)"', rels)})
        out = {}
        for ref, rid in re.findall(r'<hyperlink ref="([A-Z]+\d+)"[^>]*?r:id="([^"]+)"', self.sheet):
            if rid in tg:
                out[ref] = tg[rid].replace("&amp;", "&")
        return out

    # ---- styles « bleus » (police de la cellule de base, couleur bleue)
    def blue(self, s: str) -> str:
        if s in self.blue_cache:
            return self.blue_cache[s]
        st_ = self.styles
        xfs_m = re.search(r"<cellXfs count=\"(\d+)\">(.*?)</cellXfs>", st_, re.S)
        xfs = re.findall(r"<xf [^>]*?(?:/>|>.*?</xf>)", xfs_m.group(2), re.S)
        base = xfs[int(s)]
        font_id = int(re.search(r'fontId="(\d+)"', base).group(1))
        fonts_m = re.search(r"<fonts count=\"(\d+)\"([^>]*)>(.*?)</fonts>", st_, re.S)
        fonts = re.findall(r"<font>.*?</font>|<font/>", fonts_m.group(3), re.S)
        f = fonts[font_id]
        if "<color " in f:
            nf = re.sub(r"<color [^>]*/>", f'<color rgb="{BLUE}"/>', f, count=1)
        else:
            nf = f.replace("<font>", f'<font><color rgb="{BLUE}"/>', 1) if f != "<font/>" else f'<font><color rgb="{BLUE}"/></font>'
        new_font_id = len(fonts)
        new_fonts = fonts_m.group(0).replace(f'<fonts count="{fonts_m.group(1)}"', f'<fonts count="{new_font_id + 1}"', 1).replace("</fonts>", nf + "</fonts>")
        st_ = st_.replace(fonts_m.group(0), new_fonts, 1)
        nx = re.sub(r'fontId="\d+"', f'fontId="{new_font_id}"', base, count=1)
        if "applyFont=" not in nx:
            nx = nx.replace("<xf ", '<xf applyFont="1" ', 1)
        xfs_m = re.search(r"<cellXfs count=\"(\d+)\">(.*?)</cellXfs>", st_, re.S)
        n = int(xfs_m.group(1))
        st_ = st_.replace(xfs_m.group(0), f'<cellXfs count="{n + 1}">' + xfs_m.group(2) + nx + "</cellXfs>", 1)
        self.styles = st_
        self.blue_cache[s] = str(n)
        return str(n)

    # ---- écriture
    def save(self, out: Path):
        self.files[self.sheet_path] = self.sheet.encode("utf8")
        self.files["xl/styles.xml"] = self.styles.encode("utf8")
        tmp = out.with_name(out.name + ".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for n in self.names + [n for n in self.files if n not in self.names]:
                z.writestr(n, self.files[n])
        os.replace(tmp, out)


def inline_cell(ref, s, text):
    return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def put_cell(row_xml, ref, new_cell):
    """Remplace ou insère une cellule dans une ligne, dans l'ordre des colonnes."""
    col, _ = split_ref(ref)
    cells = [(m.group(1), m.group(0)) for m in CELL_RE.finditer(row_xml)]
    head = re.match(r"<row [^>]*?>", row_xml)
    if head is None:                                    # ligne vide auto-fermée <row .../>
        head_s = row_xml[:-2] + ">"
        cells = []
    else:
        head_s = head.group(0)
    cells = [c for c in cells if c[0] != col] + [(col, new_cell)]
    cells.sort(key=lambda c: col_num(c[0]))
    return head_s + "".join(c[1] for c in cells) + "</row>"


# --------------------------------------------------------------------------- colonnes supplémentaires
def migrate_chaleur(bk: Book, log: list):
    """La colonne P s'appelait « Chaleur » : elle devient « Conseil donné » (les rares valeurs Chaud/Tiède/Froid sont effacées)."""
    rows = bk.rows()
    head = bk.cells(rows[5])
    if bk.value(head.get("P")).strip() != "Chaleur":
        return
    sheet = bk.sheet
    sheet = sheet.replace(rows[5], put_cell(rows[5], "P5", inline_cell("P5", bk.style(head["P"]), "Conseil donné")), 1)
    cleared = []
    for r, xml in rows.items():
        if r < FIRST_ROW:
            continue
        cp = bk.cells(xml).get("P")
        if cp is not None and bk.value(cp).strip():
            cleared.append(f"ligne {r} : {bk.value(cp).strip()}")
            sheet = sheet.replace(xml, put_cell(xml, f"P{r}", f'<c r="P{r}" s="{bk.style(cp)}"/>'), 1)
    sheet = re.sub(r'<col min="16" max="16" width="[\d.]+"', '<col min="16" max="16" width="40"', sheet, count=1)
    bk.sheet = sheet
    log.append("Colonne P « Chaleur » renommée « Conseil donné »" + (" (valeurs effacées : " + "; ".join(cleared) + ")" if cleared else "") + ".")


def ensure_columns(bk: Book, log: list):
    migrate_chaleur(bk, log)
    rows = bk.rows()
    head = bk.cells(rows[5])
    titles = {c: bk.value(x) for c, x in head.items()}
    have = [c for c, t, _, _ in EXTRA if titles.get(c)]
    if len(have) == len(EXTRA):
        return
    if any(titles.get(c) and titles[c] != t for c, t, _, _ in EXTRA):
        bad = {c: titles[c] for c, t, _, _ in EXTRA if titles.get(c) and titles[c] != t}
        raise SystemExit(f"Les colonnes J à Z de « Network » contiennent déjà autre chose : {bad}. Rien n'a été modifié.")
    todo = [e for e in EXTRA if not titles.get(e[0])]
    s_head = bk.style(head.get("G"))
    sample = rows.get(FIRST_ROW) or ""
    sc = bk.cells(sample)
    s_text, s_long = bk.style(sc.get("E")), bk.style(sc.get("F"))
    sheet = bk.sheet
    last_row = max(rows)
    for r, xml in rows.items():
        if r < 5:
            continue
        new = xml
        cur = bk.cells(xml)
        for c, t, _, kind in todo:
            if c in cur and (r != 5 or titles.get(c)):
                continue
            if r == 5:
                cell = inline_cell(f"{c}5", s_head, t)
            else:
                cell = f'<c r="{c}{r}" s="{s_long if kind == "long" else s_text}"/>'
            new = put_cell(new, f"{c}{r}", cell)
        new = re.sub(r'spans="\d+:\d+"', f'spans="1:{col_num(LAST_COL)}"', new, count=1)
        sheet = sheet.replace(xml, new, 1)
    # largeurs (ID masquée)
    hid = ' hidden="1"'
    cols_add = "".join(f'<col min="{col_num(c)}" max="{col_num(c)}" width="{w}"{hid if c == ID_COL else ""} customWidth="1"/>' for c, _, w, _ in todo)
    sheet = sheet.replace("</cols>", cols_add + "</cols>", 1)
    lists = {"R": RELATIONS, "V": NIVEAUX, "W": ETUDES}
    for col, vals in lists.items():
        if any(e[0] == col for e in todo):
            sheet = add_list_validation(sheet, f"{col}6:{col}{last_row}", vals)
    if any(e[0] == "X" for e in todo):                 # nouvelles colonnes études / emploi : les anciennes D et K sont masquées
        sheet = hide_cols(sheet, [4, 11])
    bk.sheet = sheet
    extend_ranges(bk, last_row)
    log.append("Colonnes ajoutées à l'onglet Network : " + ", ".join(t for _, t, _, _ in todo) + ".")


def add_list_validation(sheet: str, sqref: str, values: list) -> str:
    dv = (f'<dataValidation type="list" allowBlank="1" showInputMessage="1" showErrorMessage="1" sqref="{sqref}">'
          f'<formula1>"{",".join(values)}"</formula1></dataValidation>')
    m = re.search(r'<dataValidations count="(\d+)"', sheet)
    if m:
        sheet = sheet.replace(m.group(0), f'<dataValidations count="{int(m.group(1)) + 1}"', 1)
        return sheet.replace("</dataValidations>", dv + "</dataValidations>", 1)
    block = f'<dataValidations count="1">{dv}</dataValidations>'
    for tag in ("<hyperlinks", "<printOptions", "<pageMargins", "<pageSetup", "</worksheet>"):
        if tag in sheet:
            return sheet.replace(tag, block + tag, 1)
    return sheet


def hide_cols(sheet: str, cols: list) -> str:
    """Masque des colonnes (numéros) dans <cols>, en découpant les plages min-max si besoin."""
    m = re.search(r"<cols>(.*?)</cols>", sheet, re.S)
    if not m:
        return sheet
    out = []
    for c in re.findall(r"<col [^>]*/>", m.group(1)):
        lo, hi = int(re.search(r'min="(\d+)"', c).group(1)), int(re.search(r'max="(\d+)"', c).group(1))
        cuts = sorted({lo, hi + 1} | {x for x in cols if lo <= x <= hi} | {x + 1 for x in cols if lo <= x <= hi})
        for a, b in zip(cuts, cuts[1:]):
            piece = re.sub(r'min="\d+"', f'min="{a}"', c, count=1)
            piece = re.sub(r'max="\d+"', f'max="{b - 1}"', piece, count=1)
            if a in cols and a == b - 1 and "hidden=" not in piece:
                piece = piece.replace("<col ", '<col hidden="1" ', 1)
            out.append(piece)
    return sheet.replace(m.group(0), "<cols>" + "".join(out) + "</cols>", 1)


def extend_ranges(bk: Book, last_row: int):
    s = bk.sheet
    s = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:{LAST_COL}{last_row}"/>', s, count=1)
    s = re.sub(r'<autoFilter ref="A5:[A-Z]+\d+"', f'<autoFilter ref="A5:{LAST_COL}{last_row}"', s, count=1)
    s = re.sub(r'sqref="A6:[A-Z]+\d+"', f'sqref="A6:{LAST_COL}{last_row}"', s)
    s = re.sub(r'sqref="H6:H\d+"', f'sqref="H6:H{last_row}"', s)
    for col in ("R", "V", "W"):
        s = re.sub(rf'sqref="{col}6:{col}\d+"', f'sqref="{col}6:{col}{last_row}"', s)
    bk.sheet = s
    wb = bk.txt("xl/workbook.xml")
    wb = re.sub(r'(<definedName name="_xlnm\._FilterDatabase" localSheetId="%d" hidden="1">)[^<]*(</definedName>)' % bk.sheet_index,
                lambda m: f"{m.group(1)}{SHEET_NAME}!$A$5:${LAST_COL}${last_row}{m.group(2)}", wb)
    if "fullCalcOnLoad" not in wb:
        wb = re.sub(r"<calcPr ", '<calcPr fullCalcOnLoad="1" ', wb, count=1)
    bk.files["xl/workbook.xml"] = wb.encode("utf8")


# --------------------------------------------------------------------------- contacts présents dans l'Excel
def date_text(v) -> str:
    """Cellule date de l'Excel -> AAAA-MM-JJ (ou le texte tel quel si ce n'est pas une date)."""
    v = (v or "").strip()
    if not v:
        return ""
    d = from_serial(v) if re.fullmatch(r"\d+(\.\d+)?", v) else nc.parse_date(v)
    return d.isoformat() if d else v


def excel_contacts(bk: Book):
    out = []
    links = bk.hyperlinks()
    for r, xml in sorted(bk.rows().items()):
        if r < FIRST_ROW:
            continue
        c = bk.cells(xml)
        nom, pre = bk.value(c.get("B")).strip(), bk.value(c.get("C")).strip()
        if not (nom or pre):
            continue
        out.append(dict(row=r, nom=nom, prenom=pre, institution=bk.value(c.get("D")), utile_pour=bk.value(c.get("E")),
                        raconte=bk.value(c.get("F")), tache=bk.value(c.get("G")),
                        echeance=date_text(bk.value(c.get("H"))), dernier_contact=date_text(bk.value(c.get("I"))),
                        rencontre_ou=bk.value(c.get("L")),
                        categorie=bk.value(c.get("J")), poste=bk.value(c.get("K")), anecdote=bk.value(c.get("M")),
                        hobbies=bk.value(c.get("N")), points_communs=bk.value(c.get("O")), conseil=bk.value(c.get("P")), relation=bk.value(c.get("R")), historique=bk.value(c.get("S")), projets=bk.value(c.get("T")),
                        ecole=bk.value(c.get("U")), niveau=bk.value(c.get("V")), etudes=bk.value(c.get("W")),
                        employeur=bk.value(c.get("X")), fonction=bk.value(c.get("Y")), associations=bk.value(c.get("Z")),
                        id=bk.value(c.get(ID_COL)).strip(), linkedin=links.get(f"C{r}", "")))
    return out


# --------------------------------------------------------------------------- import
def add_hyperlink(bk: Book, ref: str, url: str):
    rels = bk.txt(bk.rels_path) if bk.rels_path in bk.files else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
    rid = f"rId{max(ids, default=0) + 1}"
    rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{escape(url, {chr(34): "&quot;"})}" TargetMode="External"/></Relationships>')
    bk.files[bk.rels_path] = rels.encode("utf8")
    s = bk.sheet
    s = re.sub(r'<hyperlink ref="%s"[^>]*/>' % ref, "", s)
    link = f'<hyperlink ref="{ref}" r:id="{rid}"/>'
    if "<hyperlinks>" in s:
        s = s.replace("</hyperlinks>", link + "</hyperlinks>", 1)
    elif "<hyperlinks/>" in s:
        s = s.replace("<hyperlinks/>", f"<hyperlinks>{link}</hyperlinks>", 1)
    else:
        m = re.search(r"<(printOptions|pageMargins|pageSetup|headerFooter|rowBreaks|colBreaks|drawing|legacyDrawing|tableParts|extLst)\b", s)
        pos = m.start() if m else s.rindex("</worksheet>")
        s = s[:pos] + f"<hyperlinks>{link}</hyperlinks>" + s[pos:]
    bk.sheet = s


def contact_to_cells(c: dict):
    notes = c.get("raconte", "")
    if c.get("telephone"):
        notes = (notes + " · " if notes else "") + "Tél. " + c["telephone"]
    met = " · ".join(x for x in (c.get("rencontre_ou", ""), nc.fr_date(c.get("date_rencontre"))) if x)
    return {
        "B": c.get("nom", "").upper(), "C": c.get("prenom", ""), "D": c.get("institution", ""), "E": c.get("utile_pour", ""),
        "F": notes, "G": c.get("tache", ""), "H": nc.parse_date(c.get("echeance")),
        "I": nc.parse_date(c.get("dernier_contact")) or nc.parse_date(c.get("date_rencontre")),
        "J": c.get("categorie", ""), "K": c.get("poste", ""), "L": met, "M": c.get("anecdote", ""), "N": c.get("hobbies", ""),
        "O": c.get("points_communs", ""), "P": c.get("conseil", ""), "R": c.get("relation", ""), "S": c.get("historique", ""), "T": c.get("projets", ""),
        "U": c.get("ecole", ""), "V": c.get("niveau", ""), "W": c.get("etudes", ""), "X": c.get("employeur", ""), "Y": c.get("fonction", ""), "Z": c.get("associations", ""), ID_COL: c.get("id", ""),
    }


def new_empty_row(bk: Book, r: int, template_xml: str):
    """Nouvelle ligne vide (mêmes styles que la dernière ligne), avec la formule du N°."""
    cells = bk.cells(template_xml)
    out = []
    for col, x in sorted(cells.items(), key=lambda kv: col_num(kv[0])):
        s = bk.style(x)
        if col == "A":
            out.append(f'<c r="A{r}" s="{s}" t="str"><f>IF(B{r}="","",ROW()-5)</f><v></v></c>')
        else:
            out.append(f'<c r="{col}{r}" s="{s}"/>')
    head = re.match(r"<row [^>]*?>", template_xml).group(0)
    head = re.sub(r'r="\d+"', f'r="{r}"', head, count=1)
    return head + "".join(out) + "</row>"


def write_contacts(bk: Book, contacts: list, log: list):
    rows = bk.rows()
    filled = [r for r, x in rows.items() if r >= FIRST_ROW and (bk.value(bk.cells(x).get("B")).strip() or bk.value(bk.cells(x).get("C")).strip())]
    nxt = (max(filled) + 1) if filled else FIRST_ROW
    last = max(rows)
    links = bk.hyperlinks()
    link_style = next((bk.style(bk.cells(rows[r]).get("C")) for r in sorted(filled) if f"C{r}" in links), None)
    written = []
    for c in contacts:
        r = nxt
        nxt += 1
        if r > last:
            tpl = bk.rows()[last]
            bk.sheet = bk.sheet.replace("</sheetData>", new_empty_row(bk, r, tpl) + "</sheetData>", 1)
            last = r
        xml = bk.rows()[r]
        cur = bk.cells(xml)
        new = xml
        vals = contact_to_cells(c)
        for col, v in vals.items():
            if v in ("", None):
                continue
            s = bk.style(cur.get(col))
            if col == "C" and c.get("linkedin") and link_style:
                s = link_style
            sb = bk.blue(s)
            if isinstance(v, date):
                cell = f'<c r="{col}{r}" s="{sb}"><v>{serial(v)}</v></c>'
            else:
                cell = inline_cell(f"{col}{r}", sb, str(v))
            new = put_cell(new, f"{col}{r}", cell)
        a = cur.get("A")
        if a and "<f" in a:                                   # N° : on garde la formule, on met la valeur en cache
            fa = re.search(r"<f[^>]*/>|<f[^>]*>.*?</f>", a, re.S).group(0)
            new = put_cell(new, f"A{r}", f'<c r="A{r}" s="{bk.style(a)}">{fa}<v>{r - 5}</v></c>')
        bk.sheet = bk.sheet.replace(xml, new, 1)
        if c.get("linkedin"):
            add_hyperlink(bk, f"C{r}", c["linkedin"])
        written.append((r, c))
    extend_ranges(bk, last)
    for r, c in written:
        log.append(f"Ligne {r} : {c['prenom']} {c['nom'].upper()}" + (f" ({c['institution']})" if c.get("institution") else "") + " ajouté(e).")
    return written


def set_ids(bk: Book, pairs, log):
    """Écrit l'ID app dans la colonne masquée Q."""
    for r, cid in pairs:
        xml = bk.rows()[r]
        s = bk.style(bk.cells(xml).get(ID_COL))
        bk.sheet = bk.sheet.replace(xml, put_cell(xml, f"{ID_COL}{r}", inline_cell(f"{ID_COL}{r}", s, cid)), 1)
    if pairs:
        log.append(f"ID app écrit (colonne masquée Q) pour {len(pairs)} contacts déjà présents dans l'Excel.")


def pick_new(app_contacts, xl_contacts):
    ids = {c["id"] for c in xl_contacts if c["id"]}
    names = {(nc.norm(c["prenom"]).strip(), nc.norm(c["nom"]).strip()) for c in xl_contacts}
    new, same_name = [], []
    for c in app_contacts:
        if not (c.get("prenom") or c.get("nom")) or c["id"] in ids:
            continue
        if (nc.norm(c["prenom"]).strip(), nc.norm(c["nom"]).strip()) in names:
            same_name.append(c)
            continue
        new.append(c)
    new.sort(key=lambda c: c.get("cree_le", ""))
    return new, same_name


# --------------------------------------------------------------------------- Google
def google_store():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise SystemExit("Il manque gspread : pip3 install gspread google-auth tomli")
    sa, sheet_id = None, None
    sec = HERE / ".streamlit" / "secrets.toml"
    if sec.exists():
        try:
            import tomllib as toml_mod
        except ImportError:
            try:
                import tomli as toml_mod
            except ImportError:
                raise SystemExit("Pour lire .streamlit/secrets.toml : pip3 install tomli")
        data = toml_mod.loads(sec.read_text(encoding="utf8"))
        sa, sheet_id = data.get("gcp_service_account"), data.get("network_sheet_id")
    key = HERE / "cle_google.json"
    if not sa and key.exists():
        sa = json.loads(key.read_text(encoding="utf8"))
    cfg = HERE / "config.json"
    if not sheet_id and cfg.exists():
        sheet_id = json.loads(cfg.read_text(encoding="utf8")).get("network_sheet_id")
    if not sa or not sheet_id:
        raise SystemExit("Connexion Google introuvable : mets .streamlit/secrets.toml (comme l'app) dans le dossier du script.")
    creds = Credentials.from_service_account_info(dict(sa), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return nc.SheetStore(gspread.authorize(creds), sheet_id)


# --------------------------------------------------------------------------- main
def archive(xlsx: Path, log: list, stamp: datetime):
    arch = xlsx.parent / ARCHIVES_NAME / stamp.strftime("%d.%m.%Y_%Hh%M")
    if arch.exists():                                   # deux synchros dans la même minute : on ne réécrase pas la sauvegarde
        arch = arch.with_name(stamp.strftime("%d.%m.%Y_%Hh%M_%Ss"))
    arch.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xlsx, arch / (xlsx.stem + "_avant_import.xlsx"))
    md = [f"# Synchro Network du {stamp.strftime('%d.%m.%Y à %Hh%M')}", "", f"Fichier modifié : {xlsx.name} (onglet « {SHEET_NAME} »). Version d'avant : {xlsx.stem}_avant_import.xlsx (dans ce dossier).", ""]
    md += [f"- {line}" for line in log]
    (arch / "Suivi.md").write_text("\n".join(md) + "\n", encoding="utf8")
    return arch


BACKUP_DIR = "Sauvegardes Network"
BACKUP_EVERY_DAYS = 7
BACKUP_KEEP = 8


def backup_sheet(tabs: dict, xlsx: Path, stamp: datetime, force=False):
    """Copie de secours (CSV) des onglets du Google Sheet : au plus une par semaine, on garde les 8 dernières.
    tabs = {"Network": [contacts], "Saisies": [lignes du journal]}"""
    d = xlsx.parent / ARCHIVES_NAME / BACKUP_DIR
    d.mkdir(parents=True, exist_ok=True)
    files = sorted(d.glob("Network_*.csv"))
    if files and not force:
        try:
            last = date.fromisoformat(files[-1].stem[len("Network_"):len("Network_") + 10])
            if (stamp.date() - last).days < BACKUP_EVERY_DAYS:
                return []
        except ValueError:
            pass
    out = []
    for prefix, rows in tabs.items():
        path = d / f"{prefix}_{stamp.strftime('%Y-%m-%d')}.csv"
        cols = list(dict.fromkeys([k for r in rows for k in r]))
        with path.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([r.get(k, "") for k in cols])
        out.append(path)
        for old in sorted(d.glob(f"{prefix}_*.csv"))[:-BACKUP_KEEP]:
            old.unlink()
    return out


# --------------------------------------------------------------------------- synchro (l'Excel prévaut)
FIELD_COL = {"nom": "B", "prenom": "C", "institution": "D", "utile_pour": "E", "raconte": "F", "tache": "G",
             "echeance": "H", "dernier_contact": "I", "categorie": "J", "poste": "K", "rencontre_ou": "L",
             "anecdote": "M", "hobbies": "N", "points_communs": "O", "conseil": "P", "relation": "R",
             "historique": "S", "projets": "T", "ecole": "U", "niveau": "V", "etudes": "W", "employeur": "X", "fonction": "Y", "associations": "Z"}
APPEND = set(nc.APPEND_FIELDS) | {"historique"}      # textes complétés à la suite dans l'app
DATE_FIELDS = {"echeance", "dernier_contact"}


def same(field, a, b) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if field in DATE_FIELDS:
        return (nc.parse_date(a) or a) == (nc.parse_date(b) or b)
    if field in ("nom", "prenom"):
        return nc.norm(a).strip() == nc.norm(b).strip()
    return a == b


def set_cell(bk: Book, row: int, col: str, value, blue=True):
    rows = bk.rows()
    xml = rows[row]
    cur = bk.cells(xml).get(col)
    s = bk.style(cur)
    s = bk.blue(s) if blue else s
    ref = f"{col}{row}"
    if value in ("", None):
        cell = f'<c r="{ref}" s="{s}"/>'
    elif isinstance(value, date):
        cell = f'<c r="{ref}" s="{s}"><v>{serial(value)}</v></c>'
    else:
        cell = inline_cell(ref, s, str(value))
    bk.sheet = bk.sheet.replace(xml, put_cell(xml, ref, cell), 1)


def apply_changes(bk: Book, x: dict, changes: dict, log: list):
    """Reporte une modification de l'app dans l'Excel. Retourne (appliqués, ignorés)."""
    done, skipped = [], []
    r = x["row"]
    for field, pair in changes.items():
        try:
            old, new = pair
        except (TypeError, ValueError):
            continue
        old, new = ("" if old is None else str(old)), ("" if new is None else str(new))
        label = nc.LABELS.get(field, field)
        if field == "telephone":
            notes = x.get("raconte", "")
            if new and new not in notes:
                notes = (notes + " · " if notes else "") + "Tél. " + new
                set_cell(bk, r, "F", notes)
                x["raconte"] = notes
                done.append(label)
            continue
        if field == "linkedin":
            if new:
                add_hyperlink(bk, f"C{r}", new)
                done.append(label)
            continue
        col = FIELD_COL.get(field)
        if not col:
            continue                                   # champ propre à l'app (date de rencontre, etc.)
        if not same(field, old, x.get(field, "")):
            cur = (x.get(field) or "").strip()
            if field in APPEND and new.startswith(old) and len(new) > len(old):
                sep = nc.APPEND_FIELDS.get(field, "\n")
                add = new[len(old):] if old.strip() else sep + new   # l'app a ajouté du texte à la suite : on l'ajoute aussi dans l'Excel
                new = (cur + add) if cur else add.lstrip(" ·,\n")
            else:
                skipped.append(label)                  # l'Excel a été modifié entre-temps : l'Excel gagne
                continue
        if field in DATE_FIELDS:
            value = nc.parse_date(new) or new
        elif field == "nom":
            value = new.upper()
        else:
            value = new
        set_cell(bk, r, col, value)
        x[field] = new
        done.append(label)
    name = f"{x['prenom']} {x['nom'].upper()}"
    if done:
        log.append(f"Ligne {r} : {name} modifié(e) depuis l'app ({', '.join(done)}).")
    if skipped:
        log.append(f"Ligne {r} : {name}, modification de l'app ignorée pour {', '.join(skipped)} (l'Excel a changé entre-temps).")
    return done, skipped


def process_journal(bk: Book, entries: list, log: list):
    """entries = [(ligne du journal, saisie)] à synchroniser. Retourne [(ligne, statut)]."""
    marks = []
    for jr, e in entries:
        xl = excel_contacts(bk)
        by_id = {c["id"]: c for c in xl if c["id"]}
        by_name = {(nc.norm(c["prenom"]).strip(), nc.norm(c["nom"]).strip()): c for c in xl}
        action = (e.get("action") or "").strip()
        cid = (e.get("id") or "").strip()
        key = (nc.norm(e.get("prenom", "")).strip(), nc.norm(e.get("nom", "")).strip())
        if action.startswith("ajout"):
            if cid and cid in by_id:
                marks.append((jr, "déjà dans l'Excel"))
                continue
            if key in by_name and any(key):
                x = by_name[key]
                if not x["id"] and cid:
                    set_ids(bk, [(x["row"], cid)], log)      # on relie la fiche de l'app à la ligne Excel existante
                marks.append((jr, f"déjà dans l'Excel (même nom, ligne {x['row']})"))
                continue
            if not any(key):
                marks.append((jr, "ignoré : ni prénom ni nom"))
                continue
            c = nc.new_contact(**{k: e.get(k, "") for k in nc.COLUMNS})
            written = write_contacts(bk, [c], log)
            marks.append((jr, f"ajouté à l'Excel, ligne {written[0][0]}"))
        elif action == "modification":
            x = by_id.get(cid)
            if not x:
                marks.append((jr, "ignoré : contact absent de l'Excel (supprimé ?)"))
                continue
            try:
                changes = json.loads(e.get("changements") or "{}")
            except ValueError:
                marks.append((jr, "ignoré : changements illisibles"))
                continue
            done, skipped = apply_changes(bk, x, changes, log)
            if done and not skipped:
                marks.append((jr, f"appliqué dans l'Excel, ligne {x['row']}"))
            elif done:
                marks.append((jr, f"appliqué en partie, ligne {x['row']} ; ignoré (l'Excel a changé) : {', '.join(skipped)}"))
            elif skipped:
                marks.append((jr, f"ignoré, l'Excel a changé entre-temps : {', '.join(skipped)}"))
            else:
                marks.append((jr, "rien à reporter dans l'Excel"))
        else:
            marks.append((jr, f"ignoré : action inconnue « {action} »"))
    return marks


def give_ids(bk: Book, log: list):
    pairs = [(c["row"], nc.new_contact(prenom="x")["id"]) for c in excel_contacts(bk) if not c["id"]]
    if pairs:
        set_ids(bk, pairs, [])
        log.append(f"ID app donné à {len(pairs)} contact(s) de l'Excel qui n'en avaient pas (colonne Q masquée).")
    return len(pairs)


def mirror_rows(bk: Book, previous: list, journal: list):
    """L'onglet Network de l'Excel, au format de l'app. Garde la date de création connue par l'app."""
    created = {c["id"]: c.get("cree_le", "") for c in previous if c.get("id")}
    for _, e in journal:
        if (e.get("action") or "").startswith("ajout") and e.get("id"):
            created.setdefault(e["id"], e.get("cree_le", "") or e.get("horodatage", ""))
    out = []
    for x in excel_contacts(bk):
        c = {k: "" for k in nc.COLUMNS}
        for k in nc.COLUMNS:
            if k in x and k != "row":
                c[k] = "" if x[k] is None else str(x[k])
        c["cree_le"] = created.get(c["id"], "")
        out.append(c)
    return out


class Steps:
    """Affiche l'avancement dans le Terminal : [2/7] Connexion au Google Sheet… ok (1,4 s)."""

    def __init__(self, total):
        self.total, self.i, self.t0, self.t = total, 0, time.time(), None

    def go(self, label):
        self.end()
        self.i += 1
        self.t = time.time()
        print(f"[{self.i}/{self.total}] {label}…", end="", flush=True)

    def end(self, msg="ok"):
        if self.t is not None:
            print(f" {msg} ({time.time() - self.t:.1f} s)", flush=True)
            self.t = None

    def bar(self, k, n, label=""):
        w = 24
        full = int(w * k / max(n, 1))
        print(f"\r      [{'█' * full}{'░' * (w - full)}] {k}/{n} {label[:60]:<60}", end="", flush=True)

    def finish(self):
        self.end()
        print(f"Terminé en {time.time() - self.t0:.1f} s.", flush=True)


VERIF_FIELDS = ["prenom", "nom", "categorie", "relation", "associations", "ecole", "niveau", "etudes", "employeur", "fonction",
                "tache", "echeance", "dernier_contact", "rencontre_ou", "raconte", "projets", "conseil", "anecdote",
                "hobbies", "points_communs", "utile_pour", "historique", "linkedin"]


def compare(excel_rows: list, sheet_rows: list):
    """Compare l'Excel (référence) et l'onglet Réseau du Google Sheet. Retourne (manquants, en trop, différences)."""
    xs = {c["id"]: c for c in excel_rows if c.get("id")}
    gs = {c["id"]: c for c in sheet_rows if c.get("id")}
    missing = [xs[i] for i in xs if i not in gs]
    extra = [gs[i] for i in gs if i not in xs]
    diffs = []
    for i, x in xs.items():
        g = gs.get(i)
        if not g:
            continue
        for f in VERIF_FIELDS:
            a, b = str(x.get(f) or "").strip(), str(g.get(f) or "").strip()
            if a != b:
                diffs.append((x, f, a, b))
    return missing, extra, diffs


def print_compare(missing, extra, diffs, total):
    if not (missing or extra or diffs):
        print(f"Contrôle : l'app (onglet « {nc.MIRROR_TAB} ») est identique à l'Excel pour les {total} contacts.", flush=True)
        return True
    print(f"Contrôle : {len(missing)} contact(s) absent(s) de l'app, {len(extra)} en trop, {len(diffs)} case(s) différente(s).", flush=True)
    for c in missing[:20]:
        print(f"  absent de l'app : {c['prenom']} {c['nom']}")
    for c in extra[:20]:
        print(f"  dans l'app mais pas dans l'Excel : {c.get('prenom', '')} {c.get('nom', '')}")
    for x, f, a, b in diffs[:40]:
        print(f"  {x['prenom']} {x['nom']} · {nc.LABELS.get(f, f)} : Excel « {a[:50]} » / app « {b[:50]} »")
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Synchronise l'Excel et l'app Network (l'Excel prévaut).")
    ap.add_argument("--xlsx", default=str(XLSX_DEFAULT))
    ap.add_argument("--csv", help="ajouter à l'Excel les contacts de ce CSV (colonnes de l'app), sans Google")
    ap.add_argument("--simulation", action="store_true", help="n'écrit rien, affiche ce qui serait fait")
    ap.add_argument("--envoyer-excel", action="store_true", help="(ancien) même chose que la synchro normale")
    ap.add_argument("--verifier", action="store_true", help="compare l'Excel et l'app (Google Sheet) sans rien écrire")
    ap.add_argument("--sauvegarde", action="store_true", help="force une copie de secours du Google Sheet maintenant")
    ap.add_argument("--force", action="store_true", help="ignore le fichier de verrouillage d'Excel")
    a = ap.parse_args(argv)
    xlsx = Path(a.xlsx).expanduser()
    if not xlsx.exists():
        raise SystemExit(f"Excel introuvable : {xlsx}")
    lock = xlsx.with_name("~$" + xlsx.name)
    if lock.exists() and not a.force and not a.simulation and not a.verifier:
        raise SystemExit("L'Excel est ouvert : ferme-le, puis relance (ou double-clique à nouveau sur Synchroniser_Network).")

    steps = Steps(3 if (a.csv or a.verifier) else 7)
    steps.go("Lecture de l'Excel")
    bk = Book(xlsx)
    log = []
    ensure_columns(bk, log)
    stamp = datetime.now()

    # ---- mode CSV : ajout simple dans l'Excel, sans Google
    if a.csv:
        steps.go("Lecture du CSV")
        with open(a.csv, newline="", encoding="utf8") as f:
            rows = [nc.new_contact(**{k: v for k, v in r.items() if k in nc.COLUMNS}) for r in csv.DictReader(f)]
        for c in rows:
            c["id"] = ""                                  # l'ID sera donné à la prochaine synchro
        new, same_name = pick_new(rows, excel_contacts(bk))
        steps.end()
        print(f"Contacts du CSV à ajouter : {len(new)}" + (f" | ignorés (même nom) : {len(same_name)}" if same_name else ""))
        if a.simulation:
            for c in new:
                print(f"  + {c['prenom']} {c['nom'].upper()}")
            return 0
        steps.go("Écriture dans l'Excel")
        write_contacts(bk, new, log)
        if not log:
            steps.finish()
            print("Rien à faire.")
            return 0
        arch = archive(xlsx, log, stamp)
        bk.save(xlsx)
        steps.finish()
        print("\n".join(log))
        print(f"Excel mis à jour. Sauvegarde et Suivi.md : {arch}")
        return 0

    # ---- vérification seule
    if a.verifier:
        steps.go("Connexion au Google Sheet")
        store = google_store()
        steps.go("Comparaison Excel / app")
        xl_rows = mirror_rows(bk, [], [])
        sheet_rows = store.all()
        steps.end(f"{len(xl_rows)} contacts dans l'Excel, {len(sheet_rows)} dans l'app")
        m, x_, d = compare(xl_rows, sheet_rows)
        print_compare(m, x_, d, len(xl_rows))
        pend = [e for _, e in store.journal() if (e.get("statut") or "").strip() in ("", nc.A_SYNCHRONISER)]
        if pend:
            print(f"{len(pend)} saisie(s) de l'app pas encore reportée(s) dans l'Excel : lance la synchro.")
        return 0

    # ---- synchro avec le Google Sheet
    steps.go("Connexion au Google Sheet")
    store = google_store()
    steps.go("Lecture de l'app (onglets Réseau et Saisies)")
    previous = store.all()
    journal = store.journal()
    todo = [(r, e) for r, e in journal if (e.get("statut") or "").strip() in ("", nc.A_SYNCHRONISER)]
    steps.end(f"{len(previous)} contacts, {len(todo)} saisie(s) à reporter")
    steps.go("Report des saisies dans l'Excel")
    print(flush=True)
    marks = []
    for k, item in enumerate(todo, 1):
        steps.bar(k, len(todo), f"{item[1].get('prenom', '')} {item[1].get('nom', '')}")
        marks += process_journal(bk, [item], log)
    if todo:
        print(flush=True)
    deja = 0
    for (jr, e), (_, st_) in zip(todo, marks):
        if st_.startswith("déjà dans l'Excel"):
            deja += 1
            continue
        print(f"  {e.get('action', '')} · {e.get('prenom', '')} {e.get('nom', '').upper()} : {st_}")
    if deja:
        print(f"  {deja} saisie(s) déjà présentes dans l'Excel (rien à faire)")
    steps.go("Contrôle des ID et préparation de la copie pour l'app")
    give_ids(bk, log)
    mirror = mirror_rows(bk, previous, journal)
    steps.end()
    print(f"Contacts dans l'Excel, recopiés dans l'app (onglet « {nc.MIRROR_TAB} ») : {len(mirror)}")
    if a.simulation:
        if log:
            print("Changements prévus dans l'Excel :\n  " + "\n  ".join(log))
        print("Simulation : rien n'a été écrit.")
        return 0

    steps.go("Sauvegarde et écriture de l'Excel")
    if log:
        arch = archive(xlsx, log, stamp)
        bk.save(xlsx)
        steps.end()
        print("\n".join(log))
        print(f"Excel mis à jour. Sauvegarde et Suivi.md : {arch}")
    else:
        steps.end("Excel inchangé")
    for p in backup_sheet({"Network": previous, "Saisies": [e for _, e in journal]}, xlsx, stamp, force=a.sauvegarde):
        print(f"Copie de secours du Google Sheet : {p}")
    steps.go("Mise à jour de l'app (journal et onglet Réseau)")
    store.mark(marks)
    store.replace_mirror(mirror)
    steps.end()
    steps.total += 1
    steps.go("Contrôle : relecture de l'app et comparaison avec l'Excel")
    after = store.all()
    steps.end()
    m, x_, d = compare(mirror_rows(bk, previous, journal), after)
    print_compare(m, x_, d, len(mirror))
    steps.finish()
    print(f"App à jour : {len(mirror)} contacts (copie de l'Excel).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
