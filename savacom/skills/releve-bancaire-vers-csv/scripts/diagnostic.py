#!/usr/bin/env python3
"""
Caractérise n'importe quel fichier texte ou CSV : encodage, fin de ligne,
séparateur, colonnes, formats de date et de montant.

À utiliser sur tout fichier dont personne ne sait dire ce qu'il contient, et
en particulier sur un vrai export bancaire dont on veut relever le format
pour le reproduire. Ne modifie jamais le fichier.

Copie volontaire de savacom/diagnostic.py : la skill doit fonctionner seule,
une fois televersee dans claude.ai, sans le reste du depot.

    python diagnostic.py "un fichier.csv"
    python diagnostic.py *.csv

Code de sortie : 0 si tous les fichiers ont pu être analysés, 1 sinon.
"""

from __future__ import annotations

import collections
import csv
import io
import re
import sys
from pathlib import Path

BOM_UTF8 = b"\xef\xbb\xbf"
SEPARATEURS = [";", ",", "\t", "|"]
NOM_SEPARATEUR = {";": "point-virgule", ",": "virgule", "\t": "tabulation", "|": "barre"}

# Les premiers octets suffisent a nommer les formats qu'on vous tendra le plus
# souvent en croyant donner un CSV. Le NUL sert de filet pour tout le reste.
SIGNATURES = [
    (b"%PDF-", "PDF"),
    (b"PK\x03\x04", "archive ZIP (xlsx, docx, odt ?)"),
    (b"\xd0\xcf\x11\xe0", "document Office ancien (xls, doc)"),
    (b"\x89PNG", "image PNG"),
    (b"\xff\xd8\xff", "image JPEG"),
]


def detecter_binaire(brut: bytes) -> str:
    """Nomme le format binaire reconnu, ou renvoie '' si le fichier est du texte."""
    for magie, nom in SIGNATURES:
        if brut.startswith(magie):
            return nom
    if b"\x00" in brut[:4096]:
        return "fichier binaire (format non reconnu)"
    return ""


def detecter_encodage(brut: bytes) -> tuple[str, str, str]:
    """Renvoie (encodage pour lire, nom affiché, remarque).

    L'ordre compte. « utf-8-sig » décode aussi bien un fichier SANS BOM :
    l'essayer en premier ferait passer tout UTF-8 pour un fichier à BOM et
    rendrait la branche UTF-8 inatteignable. On teste donc le BOM sur les
    octets, puis l'UTF-8 strict, puis les encodages Windows.
    """
    if not brut:
        return "utf-8", "indeterminable", "fichier vide"

    if brut.startswith(BOM_UTF8):
        return ("utf-8-sig", "UTF-8 avec BOM",
                "le BOM pollue le premier champ si on ne le retire pas")

    try:
        brut.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        accents = sum(1 for b in brut if b > 127)
        if accents:
            return ("utf-8", "UTF-8 sans BOM",
                    f"{accents} octets accentues ; WinBiz attend de l'ANSI 1252")
        return ("utf-8", "ASCII", "aucun caractere accentue, compatible partout")

    for enc, nom in (("cp1252", "Windows-1252 (ANSI)"), ("latin-1", "ISO 8859-1")):
        try:
            brut.decode(enc)
        except UnicodeDecodeError:
            continue
        return enc, nom, "l'UTF-8 echoue : c'est bien un encodage Windows"

    return "latin-1", "indetermine", "aucun encodage ne convient proprement"


def detecter_separateur(texte: str) -> tuple[str, dict]:
    """Le bon séparateur est celui qui donne un nombre de colonnes constant."""
    lignes = [l for l in texte.splitlines() if l.strip()][:60]
    if not lignes:
        return "", {}
    scores = {}
    for sep in SEPARATEURS:
        try:
            rows = list(csv.reader(lignes, delimiter=sep))
        except csv.Error:
            continue
        largeurs = collections.Counter(len(r) for r in rows)
        if not largeurs:
            continue
        dominante, occurrences = largeurs.most_common(1)[0]
        if dominante < 2:
            continue
        scores[sep] = (occurrences / len(rows), dominante, dict(largeurs))
    if not scores:
        return "", {}
    meilleur = max(scores, key=lambda s: (scores[s][0], scores[s][1]))
    return meilleur, scores


def analyser_colonne(valeurs: list[str]) -> str:
    """Devine ce que contient une colonne, à partir de ses valeurs."""
    v = [x.strip() for x in valeurs if x.strip()]
    if not v:
        return "toujours vide"
    ech = v[:200]

    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T].*)?", x) for x in ech):
        return "date AAAA-MM-JJ"
    if all(re.fullmatch(r"\d{2}[./]\d{2}[./]\d{2,4}", x) for x in ech):
        return "date JJ.MM.AAAA"
    if all(re.fullmatch(r"-?[\d']+[.,]\d{1,2}|-?[\d']+", x) for x in ech):
        apo = any("'" in x for x in ech)
        virgule = sum(1 for x in ech if "," in x)
        point = sum(1 for x in ech if "." in x)
        detail = []
        if apo:
            detail.append("apostrophe de milliers")
        if virgule and point:
            detail.append("MELANGE virgule et point decimaux")
        elif virgule:
            detail.append("virgule decimale")
        elif point:
            detail.append("point decimal")
        else:
            detail.append("aucune decimale")
        # Compter les decimales quel que soit le separateur employe.
        dec = collections.Counter(
            len(re.split(r"[.,]", x)[-1]) if re.search(r"[.,]", x) else 0
            for x in ech
        )
        detail.append(f"decimales {sorted(dec)}" if len(dec) > 1
                      else f"{list(dec)[0]} decimale(s)")
        if any(x.startswith("-") for x in ech):
            detail.append("signe negatif present")
        return "montant — " + ", ".join(detail)
    if all(re.fullmatch(r"[A-Z]{2}[0-9A-Z ]{13,32}", x) for x in ech):
        return "IBAN"
    if all(re.fullmatch(r"\d+", x) for x in ech):
        return "entier"

    longueurs = [len(x) for x in ech]
    return (f"texte — {min(longueurs)} a {max(longueurs)} caracteres, "
            f"{len(set(v))} valeur(s) distincte(s)")


def diagnostiquer(chemin: Path) -> None:
    brut = chemin.read_bytes()
    print("=" * 74)
    print(f"  {chemin.name}")
    print("=" * 74)
    print(f"  taille           : {len(brut):,} octets".replace(",", "'"))

    if not brut:
        print("  NATURE           : fichier vide, rien a analyser.")
        return

    binaire = detecter_binaire(brut)
    if binaire:
        print(f"  NATURE           : {binaire}")
        print("                     ce n'est pas un fichier texte : analyse interrompue.")
        print("                     rien n'a ete lu, donc aucun encodage n'est annonce.")
        return

    enc, nom, note = detecter_encodage(brut)
    print(f"  encodage         : {nom}")
    print(f"                     {note}")

    crlf = brut.count(b"\r\n")
    lf = brut.count(b"\n") - crlf
    if crlf and not lf:
        fin = "CRLF (Windows)"
    elif lf and not crlf:
        fin = "LF (Unix)"
    elif not crlf and not lf:
        fin = "aucune fin de ligne (fichier d'une seule ligne)"
    else:
        fin = f"MELANGE — {crlf} CRLF et {lf} LF"
    print(f"  fin de ligne     : {fin}")

    texte = brut.decode(enc, errors="replace")
    lignes = texte.splitlines()
    print(f"  lignes           : {len(lignes)}")

    sep, scores = detecter_separateur(texte)
    if not sep:
        print("  separateur       : aucun — ce fichier n'est pas tabulaire")
        print("\n  20 premieres lignes :")
        for l in lignes[:20]:
            print("   ", l[:100])
        return
    coherence, largeur, _ = scores[sep]
    print(f"  separateur       : {NOM_SEPARATEUR[sep]}  "
          f"({coherence:.0%} des lignes ont {largeur} colonnes)")

    rows = list(csv.reader(io.StringIO(texte, newline=""), delimiter=sep))

    i_table = 0
    for i, r in enumerate(rows[:40]):
        if len(r) == largeur and sum(1 for c in r if c.strip()) >= largeur - 1:
            i_table = i
            break
    if i_table:
        print(f"\n  ATTENTION : {i_table} ligne(s) avant la table (metadonnees).")
        for l in lignes[:i_table]:
            if l.strip():
                print("     ", l[:90])

    entete = rows[i_table]
    corps = [r for r in rows[i_table + 1:] if r and any(c.strip() for c in r)]
    print(f"\n  colonnes         : {len(entete)}")
    print(f"  lignes de donnees: {len(corps)}")
    if not corps:
        print("  NATURE           : en-tete sans aucune ligne de donnees.")
        return

    reparties = collections.Counter(len(r) for r in corps)
    if len(reparties) > 1:
        print(f"  IRREGULIER       : {dict(reparties)} — colonnes non constantes")

    quotes = sum(1 for r in corps for c in r if sep in c)
    if quotes:
        print(f"  PIEGE            : {quotes} champ(s) contiennent le separateur")
        print("                     un decoupage naif casserait ces lignes")

    multi = sum(1 for r in corps for c in r if "\n" in c)
    if multi:
        print(f"  PIEGE            : {multi} champ(s) contiennent un retour a la ligne")

    vides = [r for r in corps if not r[0].strip()]
    if vides:
        print(f"  A VERIFIER       : {len(vides)} ligne(s) sans valeur en 1re colonne")
        print("                     souvent des sous-lignes rattachees a la precedente")

    print("\n  COLONNES")
    print("  " + "-" * 70)
    for i, nom_col in enumerate(entete):
        vals = [r[i] for r in corps if len(r) > i]
        remplies = sum(1 for x in vals if x.strip())
        taux = f"{remplies}/{len(vals)}" if vals else "0/0"
        titre = (nom_col.strip() or "(sans titre)")[:26]
        print(f"   [{i:2}] {titre:<26} {taux:>9}  {analyser_colonne(vals)}")

    print("\n  3 PREMIERES LIGNES")
    print("  " + "-" * 70)
    for r in corps[:3]:
        for i, c in enumerate(r):
            if c.strip():
                print(f"   [{i:2}] {c[:78]}")
        print("   " + "." * 40)
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    code = 0
    for arg in sys.argv[1:]:
        chemin = Path(arg)
        if not chemin.is_file():
            print(f"!! introuvable : {arg}")
            code = 1
            continue
        try:
            diagnostiquer(chemin)
        except Exception as e:
            print(f"!! {chemin.name} : {type(e).__name__} — {e}")
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
