#!/usr/bin/env python3
"""
Convertit un export UBS e-banking (« transactions(n).csv ») en fichier
d'importation d'écritures WinBiz.

Principe directeur : ce script ne devine rien. Tout ce qu'il ne peut pas
établir avec certitude part sur un compte d'attente et ressort dans le
rapport. Une donnée douteuse n'est jamais présentée comme correcte.

Usage :
    python ubs_vers_winbiz.py transactions13.csv --compte-banque 1020

Sortie :
    <fichier>_winbiz.csv   fichier d'importation (ANSI 1252, CRLF, « ; »)
    <fichier>_rapport.txt  contrôles, anomalies, lignes à imputer
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# --- Format d'entrée : constaté sur les fichiers réels, pas supposé ---------
ENTREE_ENCODAGE = "utf-8-sig"  # UTF-8 avec BOM
SEPARATEUR = ";"
COL_ENTETE = "Date de transaction"  # marque le début de la table

# Index des colonnes de l'export UBS (15 colonnes, la dernière vide)
C_DATE_TRANS, C_HEURE, C_DATE_COMPTA, C_DATE_VALEUR = 0, 1, 2, 3
C_DEVISE, C_DEBIT, C_CREDIT, C_SOUS_MONTANT, C_SOLDE = 4, 5, 6, 7, 8
C_NO_TRANS, C_DESC1, C_DESC2, C_DESC3 = 9, 10, 11, 12

# --- Format de sortie WinBiz : à confirmer chez le client ------------------
# Documentation Winbiz : texte séparé « ; », ANSI 1252, CRLF.
# Colonnes 1 à 7 pour une écriture sans TVA ni devise étrangère.
SORTIE_ENCODAGE = "cp1252"
SORTIE_FIN_LIGNE = "\r\n"
COLONNES_WINBIZ = ["Date", "Piece", "Debit", "Credit", "Libelle", "Montant", "Journal"]

# Caractères que le cp1252 ne sait pas représenter : on translittère
# volontairement plutôt que de les perdre en silence.
TRANSLITTERATION = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
    " ": " ", "‑": "-",
}


@dataclass
class Ecriture:
    """Une écriture comptable, issue d'une ligne mère de l'export."""
    date: str                       # JJ.MM.AAAA
    piece: str
    libelle: str
    montant: float                  # toujours positif ; le sens vient des comptes
    sens: str                       # "debit_banque" (encaissement) | "credit_banque"
    references: list[str] = field(default_factory=list)
    remarques: list[str] = field(default_factory=list)

    @property
    def a_imputer(self) -> bool:
        return any(r.startswith("IMPUTER") for r in self.remarques)


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def lire_export(chemin: Path) -> tuple[dict[str, str], list[list[str]]]:
    """Renvoie (métadonnées d'en-tête, lignes de la table).

    On lit avec le module csv et jamais avec split(';') : 1754 champs de ce
    fichier contiennent un « ; » à l'intérieur de guillemets. Un split naïf
    décale toutes les colonnes suivantes sans lever la moindre erreur.
    """
    with open(chemin, encoding=ENTREE_ENCODAGE, newline="") as f:
        texte = f.read()
    lignes = list(csv.reader(texte.splitlines(), delimiter=SEPARATEUR))

    try:
        i_entete = next(i for i, r in enumerate(lignes) if r and r[0] == COL_ENTETE)
    except StopIteration:
        raise SystemExit(
            f"{chemin.name} : en-tête « {COL_ENTETE} » introuvable. "
            "Ce fichier n'est pas un export UBS au format attendu."
        )

    meta = {r[0].rstrip(":"): r[1] for r in lignes[:i_entete] if len(r) > 1 and r[0]}
    table = [r for r in lignes[i_entete + 1:] if r and any(c.strip() for c in r)]
    return meta, table


def grouper(table: list[list[str]]) -> list[tuple[list[str], list[list[str]]]]:
    """Regroupe chaque ligne mère avec ses sous-lignes.

    Une sous-ligne se reconnaît à sa date vide. Elle décompose un versement
    collectif : plusieurs clients ont payé, la banque a crédité en une fois.
    Vérifié sur les données réelles : somme(sous-montants) == montant mère,
    102 fois sur 102. Les sous-lignes ne sont donc PAS des écritures
    supplémentaires. Les compter en produirait le double.
    """
    groupes: list[tuple[list[str], list[list[str]]]] = []
    for ligne in table:
        if ligne[C_DATE_TRANS].strip():
            groupes.append((ligne, []))
        elif groupes:
            groupes[-1][1].append(ligne)
        else:
            raise SystemExit("Sous-ligne orpheline en tête de fichier : format inattendu.")
    return groupes


# ---------------------------------------------------------------------------
# Contrôles — les invariantes du fichier, indépendantes de ce script
# ---------------------------------------------------------------------------

def controler_chaine_soldes(groupes) -> list[str]:
    """solde[i] == solde[i+1] + montant[i] (le fichier est anti-chronologique).

    Détecte toute ligne perdue, dupliquée ou de signe inversé. Vérifié :
    0 rupture sur 769 transitions du fichier de référence.
    """
    anomalies = []
    meres = [m for m, _ in groupes]
    for i in range(len(meres) - 1):
        try:
            solde_i = float(meres[i][C_SOLDE])
            solde_suivant = float(meres[i + 1][C_SOLDE])
            montant = float(meres[i][C_DEBIT] or meres[i][C_CREDIT] or 0)
        except ValueError:
            anomalies.append(f"ligne {i + 1} : solde ou montant illisible")
            continue
        if abs(round(solde_suivant + montant, 2) - round(solde_i, 2)) > 0.005:
            anomalies.append(
                f"ligne {i + 1} ({meres[i][C_DATE_TRANS]}) : rupture de solde — "
                f"{solde_suivant} + {montant} != {solde_i}"
            )
    return anomalies


def controler_sous_montants(groupes) -> list[str]:
    """somme(sous-montants) == montant de la ligne mère."""
    anomalies = []
    for mere, sous in groupes:
        if not sous:
            continue
        try:
            total = sum(float(s[C_SOUS_MONTANT]) for s in sous if s[C_SOUS_MONTANT].strip())
            montant = abs(float(mere[C_DEBIT] or mere[C_CREDIT] or 0))
        except ValueError:
            anomalies.append(f"{mere[C_DATE_TRANS]} : sous-montant illisible")
            continue
        if abs(abs(total) - montant) > 0.005:
            anomalies.append(
                f"{mere[C_DATE_TRANS]} {mere[C_DESC1][:40]} : "
                f"somme des sous-montants {total:.2f} != montant mère {montant:.2f}"
            )
    return anomalies


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def assainir(texte: str, longueur_max: int) -> tuple[str, str | None]:
    """Prépare un texte pour le cp1252. Renvoie (texte, remarque éventuelle).

    Le séparateur est retiré du contenu, jamais échappé par des guillemets.
    Le module csv de Python sait produire "champ;avec;separateur" selon la
    RFC 4180, mais rien ne garantit qu'un importateur métier ancien sache le
    relire : beaucoup découpent bêtement sur « ; ». Un champ échappé devient
    alors trois colonnes et l'import casse.

    Ce n'est pas théorique ici : 640 des 760 libellés UBS contiennent un
    « ; ». L'export Raiffeisen, lui, n'en contient aucun — ce qui pourrait
    expliquer à lui seul « Raiffeisen OK / UBS KO ».
    """
    for source, cible in TRANSLITTERATION.items():
        texte = texte.replace(source, cible)
    texte = texte.replace(SEPARATEUR, ",").replace('"', "'")
    texte = " ".join(texte.split())

    perdus = []
    sortie = []
    for c in texte:
        try:
            c.encode(SORTIE_ENCODAGE)
            sortie.append(c)
        except UnicodeEncodeError:
            remplacement = unicodedata.normalize("NFKD", c)
            remplacement = "".join(x for x in remplacement if not unicodedata.combining(x))
            try:
                remplacement.encode(SORTIE_ENCODAGE)
            except UnicodeEncodeError:
                remplacement = "?"
            perdus.append(c)
            sortie.append(remplacement)

    resultat = "".join(sortie)
    remarque = None
    if perdus:
        remarque = f"caracteres non representables en cp1252 translitteres : {''.join(perdus)}"
    if len(resultat) > longueur_max:
        resultat = resultat[:longueur_max]
        remarque = (remarque + " ; " if remarque else "") + f"libelle tronque a {longueur_max}"
    return resultat, remarque


def convertir_date(iso: str) -> str:
    """2026-08-09 -> 09.08.2026"""
    a, m, j = iso.split("-")
    return f"{j}.{m}.{a}"


def construire_ecritures(groupes, longueur_libelle: int, longueur_piece: int) -> list[Ecriture]:
    ecritures = []
    for mere, sous in groupes:
        debit = mere[C_DEBIT].strip()
        credit = mere[C_CREDIT].strip()
        montant = float(debit or credit or 0)

        if montant == 0:
            continue  # lignes « Solde décompte des prix prestations » à 0.00

        # Le libellé utile : Description1, complété de Description2 quand
        # celle-ci porte le nom de la contrepartie plutôt qu'un code technique.
        parties = [mere[C_DESC1].strip()]
        desc2 = mere[C_DESC2].strip()
        if desc2 and not desc2.startswith(("20326812", "FILETRANSFER")):
            parties.append(desc2.replace("\n", " "))
        libelle_brut = " ".join(p for p in parties if p)

        libelle, remarque = assainir(libelle_brut, longueur_libelle)
        remarques = [remarque] if remarque else []

        # Tronquer par la FIN, pas par le début : sur cet export les numéros
        # de transaction ne diffèrent que par leurs derniers caractères
        # (0104216DN2553368 vs 0104216DN2553365). Couper à gauche fabriquait
        # 12 collisions sur le fichier de référence, donc 12 paires
        # d'écritures partageant le même numéro de pièce.
        no_trans = mere[C_NO_TRANS].strip()
        piece = no_trans[-longueur_piece:] if longueur_piece else no_trans
        if len(no_trans) > len(piece):
            remarques.append(f"numero de transaction tronque a {longueur_piece} caracteres")

        references = [
            s[C_DESC1].strip() for s in sous
            if s[C_DESC1].strip().startswith("QRR:")
        ]

        date_source = mere[C_DATE_COMPTA].strip() or mere[C_DATE_TRANS].strip()
        if not mere[C_DATE_COMPTA].strip():
            remarques.append("date de comptabilisation absente : date de transaction utilisee")

        remarques.append("IMPUTER : contrepartie a determiner")

        ecritures.append(Ecriture(
            date=convertir_date(date_source),
            piece=piece,
            libelle=libelle,
            montant=abs(montant),
            sens="debit_banque" if credit else "credit_banque",
            references=references,
            remarques=remarques,
        ))
    return ecritures


def desambiguer_pieces(ecritures, longueur_piece: int) -> list[str]:
    """Rend chaque numero de piece unique, de facon deterministe.

    UBS reutilise un meme numero de transaction pour un virement et ses
    « Frais de tiers » : 3 cas dans le fichier de reference. La collision
    vient donc de la source, pas de la troncature. On suffixe les doublons
    plutot que de les laisser passer : un numero de piece partage empeche de
    retrouver une ecriture et casse toute reprise apres un import partiel.
    """
    compteur: dict[str, int] = {}
    remarques = []
    for e in ecritures:
        base = e.piece
        n = compteur.get(base, 0)
        compteur[base] = n + 1
        if n == 0:
            continue
        suffixe = f"-{n}"
        budget = (longueur_piece - len(suffixe)) if longueur_piece else len(base)
        e.piece = base[-budget:] + suffixe
        e.remarques.append(f"numero de piece '{base}' deja utilise, suffixe en '{e.piece}'")
        remarques.append(
            f"{e.date} {e.montant:>10.2f} {e.libelle[:35]} : "
            f"numero UBS '{base}' partage, renomme '{e.piece}'"
        )
    return remarques


def ecrire_winbiz(ecritures, chemin, compte_banque, compte_attente, journal, entete):
    """Écrit le fichier d'importation.

    Sens comptable :
      - encaissement  -> débit banque   / crédit compte d'attente
      - décaissement  -> débit attente  / crédit banque
    Le montant est toujours positif : le sens est porté par les comptes.
    """
    with open(chemin, "w", encoding=SORTIE_ENCODAGE, newline="") as f:
        w = csv.writer(f, delimiter=SEPARATEUR, lineterminator=SORTIE_FIN_LIGNE)
        if entete:
            w.writerow(COLONNES_WINBIZ)
        for e in ecritures:
            if e.sens == "debit_banque":
                cpt_debit, cpt_credit = compte_banque, compte_attente
            else:
                cpt_debit, cpt_credit = compte_attente, compte_banque
            ligne = [e.date, e.piece, cpt_debit, cpt_credit,
                     e.libelle, f"{e.montant:.2f}", journal]
            # Garde-fou : aucun champ ne doit contenir le separateur, sinon
            # csv l'echapperait par des guillemets et l'importateur WinBiz
            # decouperait la ligne au mauvais endroit.
            for champ in ligne:
                if SEPARATEUR in str(champ) or '"' in str(champ):
                    raise SystemExit(
                        f"Bug interne : le champ {champ!r} contient le separateur. "
                        "Corriger assainir() avant d'importer quoi que ce soit."
                    )
            w.writerow(ligne)


def ecrire_rapport(chemin, source, meta, ecritures, anomalies_solde, anomalies_sous,
                   groupes, remarques_piece):
    lignes = [
        "RAPPORT DE CONVERSION UBS -> WINBIZ",
        "=" * 70,
        f"Fichier source : {source.name}",
        f"Compte         : {meta.get('IBAN', 'inconnu')}",
        f"Solde final    : {meta.get('Solde final', 'inconnu')}",
        "",
        "CONTROLES",
        "-" * 70,
        f"  Transactions lues                  : {len(groupes)}",
        f"  Ecritures produites                : {len(ecritures)}",
        f"  Lignes a 0.00 ecartees             : {len(groupes) - len(ecritures)}",
        f"  Versements collectifs regroupes    : {sum(1 for _, s in groupes if s)}",
        f"  Chaine des soldes                  : "
        f"{'OK' if not anomalies_solde else str(len(anomalies_solde)) + ' RUPTURE(S)'}",
        f"  Sous-montants et num. de piece     : "
        f"{'OK' if not anomalies_sous else str(len(anomalies_sous)) + ' ECART(S)'}",
        "",
    ]

    total_debit = sum(e.montant for e in ecritures if e.sens == "credit_banque")
    total_credit = sum(e.montant for e in ecritures if e.sens == "debit_banque")
    lignes += [
        f"  Total des decaissements            : {total_debit:>12,.2f} CHF".replace(",", "'"),
        f"  Total des encaissements            : {total_credit:>12,.2f} CHF".replace(",", "'"),
        f"  Variation nette                    : {total_credit - total_debit:>12,.2f} CHF".replace(",", "'"),
        "",
    ]

    if anomalies_solde or anomalies_sous:
        lignes += ["ANOMALIES BLOQUANTES", "-" * 70]
        lignes += [f"  ! {a}" for a in anomalies_solde + anomalies_sous] + [""]

    a_imputer = [e for e in ecritures if e.a_imputer]
    lignes += [
        "A IMPUTER MANUELLEMENT DANS WINBIZ",
        "-" * 70,
        f"  {len(a_imputer)} ecriture(s) portent le compte d'attente en contrepartie.",
        "  Ce script n'attribue aucun compte de charge : c'est une decision",
        "  comptable, pas une transformation de donnees.",
        "",
    ]

    if remarques_piece:
        lignes += [
            "NUMEROS DE PIECE DESAMBIGUISES",
            "-" * 70,
            f"  {len(remarques_piece)} collision(s) presente(s) dans l'export UBS lui-meme.",
        ] + [f"  {r}" for r in remarques_piece] + [""]

    avec_ref = [e for e in ecritures if e.references]
    if avec_ref:
        lignes += [
            "REFERENCES QR DISPONIBLES POUR LE RAPPROCHEMENT",
            "-" * 70,
            f"  {len(avec_ref)} encaissement(s) portent une ou plusieurs references QR.",
            "",
        ]
        for e in avec_ref[:15]:
            lignes.append(f"  {e.date}  {e.montant:>10.2f}  {e.libelle[:32]}")
            for r in e.references:
                lignes.append(f"                             {r}")
        if len(avec_ref) > 15:
            lignes.append(f"  ... et {len(avec_ref) - 15} autre(s).")
        lignes.append("")

    autres = [(e, r) for e in ecritures for r in e.remarques if not r.startswith("IMPUTER")]
    if autres:
        lignes += ["REMARQUES DE TRANSFORMATION", "-" * 70]
        for e, r in autres[:20]:
            lignes.append(f"  {e.date} {e.piece} : {r}")
        if len(autres) > 20:
            lignes.append(f"  ... et {len(autres) - 20} autre(s).")

    Path(chemin).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", type=Path, help="export UBS transactions(n).csv")
    p.add_argument("--compte-banque", default="1020", help="compte bancaire au plan comptable")
    p.add_argument("--compte-attente", default="9999", help="contrepartie provisoire")
    p.add_argument("--journal", default="", help="code journal WinBiz (colonne 7)")
    p.add_argument("--longueur-libelle", type=int, default=60)
    p.add_argument("--longueur-piece", type=int, default=15,
                   help="0 pour ne pas tronquer")
    p.add_argument("--entete", action="store_true", help="ecrire la ligne d'en-tete")
    p.add_argument("-o", "--sortie", type=Path)
    args = p.parse_args()

    meta, table = lire_export(args.source)
    groupes = grouper(table)

    anomalies_solde = controler_chaine_soldes(groupes)
    anomalies_sous = controler_sous_montants(groupes)

    ecritures = construire_ecritures(groupes, args.longueur_libelle, args.longueur_piece)
    remarques_piece = desambiguer_pieces(ecritures, args.longueur_piece)

    sortie = args.sortie or args.source.with_name(args.source.stem + "_winbiz.csv")
    rapport = sortie.with_name(sortie.stem.replace("_winbiz", "") + "_rapport.txt")

    ecrire_winbiz(ecritures, sortie, args.compte_banque, args.compte_attente,
                  args.journal, args.entete)
    ecrire_rapport(rapport, args.source, meta, ecritures,
                   anomalies_solde, anomalies_sous, groupes, remarques_piece)

    print(f"{len(ecritures)} ecritures -> {sortie}")
    print(f"rapport -> {rapport}")
    if anomalies_solde or anomalies_sous:
        print(f"ATTENTION : {len(anomalies_solde) + len(anomalies_sous)} anomalie(s), "
              f"voir le rapport avant d'importer.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
