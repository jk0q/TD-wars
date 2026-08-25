#!/usr/bin/env python3
"""
Caractérise n'importe quel fichier texte ou CSV : encodage, fin de ligne,
séparateur, colonnes, formats de date et de montant.

À utiliser sur place, sur tout fichier qu'on vous tend et dont personne ne
sait dire ce qu'il contient. Ne modifie jamais le fichier.

    python diagnostic.py "un fichier.csv"
    python diagnostic.py *.csv
"""

from __future__ import annotations

import collections
import csv
import io
import re
import sys
from pathlib import Path

ENCODAGES = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
SEPARATEURS = [";", ",", "\t", "|"]


def detecter_encodage(brut: bytes) -> tuple[str, str]:
    """Renvoie (encodage retenu, remarque)."""
    if brut.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", "BOM UTF-8 present — attention, il pollue le 1er champ"
    for enc in ENCODAGES:
        try:
            brut.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == "utf-8":
            accents = sum(1 for b in brut if b > 127)
            return enc, f"UTF-8 sans BOM ({accents} octets accentues)"
        return enc, f"{enc} (l'UTF-8 echoue, donc encodage Windows)"
    return "latin-1", "aucun encodage propre — latin-1 par defaut"


def detecter_separateur(texte: str) -> tuple[str, dict]:
    """Le bon séparateur est celui qui donne un nombre de colonnes constant."""
    lignes = [l for l in texte.splitlines() if l.strip()][:60]
    scores = {}
    for sep in SEPARATEURS:
        try:
            rows = list(csv.reader(lignes, delimiter=sep))
        except csv.Error:
            continue
        largeurs = collections.Counter(len(r) for r in rows)
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
        virg = any("," in x for x in ech)
        dec = collections.Counter(
            len(x.split(".")[-1]) if "." in x else 0 for x in ech
        )
        detail = []
        if apo:
            detail.append("apostrophe de milliers")
        detail.append("virgule decimale" if virg else "point decimal")
        if len(dec) > 1:
            detail.append(f"decimales variables {sorted(dec)}")
        else:
            detail.append(f"{list(dec)[0]} decimale(s)")
        if any(x.startswith("-") for x in ech):
            detail.append("signe negatif present")
        return "montant — " + ", ".join(detail)
    if all(re.fullmatch(r"[A-Z]{2}[0-9A-Z ]{13,32}", x) for x in ech):
        return "IBAN"
    if all(re.fullmatch(r"\d+", x) for x in ech):
        return "entier"

    longueurs = [len(x) for x in ech]
    uniques = len(set(v))
    return (
        f"texte — {min(longueurs)} a {max(longueurs)} caracteres, "
        f"{uniques} valeur(s) distincte(s)"
    )


def diagnostiquer(chemin: Path) -> None:
    brut = chemin.read_bytes()
    print("=" * 74)
    print(f"  {chemin.name}")
    print("=" * 74)
    print(f"  taille           : {len(brut):,} octets".replace(",", "'"))

    enc, note = detecter_encodage(brut)
    print(f"  encodage         : {enc}")
    print(f"                     {note}")

    crlf = brut.count(b"\r\n")
    lf = brut.count(b"\n") - crlf
    fin = "CRLF (Windows)" if crlf and not lf else "LF (Unix)" if lf and not crlf else f"MELANGE — {crlf} CRLF et {lf} LF"
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
    nom_sep = {";": "point-virgule", ",": "virgule", "\t": "tabulation", "|": "barre"}[sep]
    coherence, largeur, largeurs = scores[sep]
    print(f"  separateur       : {nom_sep}  ({coherence:.0%} des lignes ont {largeur} colonnes)")

    rows = list(csv.reader(lignes, delimiter=sep))

    # Où commence vraiment la table ?
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

    reparties = collections.Counter(len(r) for r in corps)
    if len(reparties) > 1:
        print(f"  IRREGULIER       : {dict(reparties)} — colonnes non constantes")

    quotes = sum(1 for r in corps for c in r if sep in c)
    if quotes:
        print(f"  PIEGE            : {quotes} champ(s) contiennent le separateur")
        print("                     un decoupage naif casserait ces lignes")

    vides = [r for r in corps if not r[0].strip()]
    if vides:
        print(f"  A VERIFIER       : {len(vides)} ligne(s) sans valeur en 1re colonne")
        print("                     souvent des sous-lignes rattachees a la precedente")

    print("\n  COLONNES")
    print("  " + "-" * 70)
    for i, nom in enumerate(entete):
        vals = [r[i] for r in corps if len(r) > i]
        remplies = sum(1 for x in vals if x.strip())
        taux = f"{remplies}/{len(vals)}" if vals else "0/0"
        print(f"   [{i:2}] {(nom.strip() or '(sans titre)')[:26]:<26} {taux:>9}  {analyser_colonne(vals)}")

    print("\n  3 PREMIERES LIGNES")
    print("  " + "-" * 70)
    for r in corps[:3]:
        for i, c in enumerate(r):
            if c.strip():
                print(f"   [{i:2}] {c[:78]}")
        print("   " + "·" * 40)
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(errors="replace")
    for arg in sys.argv[1:]:
        chemin = Path(arg)
        if not chemin.is_file():
            print(f"!! introuvable : {arg}")
            continue
        try:
            diagnostiquer(chemin)
        except Exception as e:
            print(f"!! {chemin.name} : {type(e).__name__} — {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
