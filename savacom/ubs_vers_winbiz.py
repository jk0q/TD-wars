#!/usr/bin/env python3
"""
Convertit un export UBS e-banking (« transactions(n).csv ») en fichier
d'importation d'écritures WinBiz.

Principe directeur : ce script ne devine rien et ne produit jamais un fichier
plausible mais faux. Tout ce qu'il ne peut pas établir avec certitude part sur
un compte d'attente et ressort dans le rapport ; tout ce qui violerait une
invariante arrête le traitement avant qu'un octet ne soit écrit.

Usage :
    python ubs_vers_winbiz.py transactions13.csv --compte-banque 1020

Sortie :
    <fichier>_winbiz.csv   fichier d'importation (ANSI 1252, CRLF, « ; »)
    <fichier>_rapport.txt  contrôles, anomalies, lignes à imputer

Avec --limite, les noms portent « _TEST » : un fichier partiel ne doit jamais
occuper la place du fichier de production.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# --- Format d'entrée : constaté sur les fichiers réels, pas supposé ---------
# Meme vocabulaire que diagnostic.py : le BOM se teste sur les octets, pas en
# essayant « utf-8-sig » en premier — il decode aussi les fichiers sans BOM.
BOM_UTF8 = b"\xef\xbb\xbf"
ENCODAGES_ESSAYES = [("utf-8", "UTF-8 sans BOM"),
                     ("cp1252", "Windows-1252 (ANSI)"),
                     ("latin-1", "ISO 8859-1")]
SEPARATEUR = ";"
COL_ENTETE = "Date de transaction"  # marque le début de la table

# Index des colonnes de l'export UBS (15 colonnes, la dernière vide)
C_DATE_TRANS, C_HEURE, C_DATE_COMPTA, C_DATE_VALEUR = 0, 1, 2, 3
C_DEVISE, C_DEBIT, C_CREDIT, C_SOUS_MONTANT, C_SOLDE = 4, 5, 6, 7, 8
C_NO_TRANS, C_DESC1, C_DESC2, C_DESC3 = 9, 10, 11, 12
COLONNES_REQUISES = C_DESC2 + 1  # plus haut index réellement lu, +1

# --- Format de sortie WinBiz : à confirmer chez le client ------------------
# Documentation Winbiz : texte séparé « ; », ANSI 1252, CRLF.
# Colonnes 1 à 7 pour une écriture sans TVA ni devise étrangère.
SORTIE_ENCODAGE = "cp1252"
SORTIE_FIN_LIGNE = "\r\n"
COLONNES_WINBIZ = ["Date", "Piece", "Debit", "Credit", "Libelle", "Montant", "Journal"]

LONGUEUR_PIECE_MINIMALE = 4  # en deçà, un numéro tronqué ne distingue plus rien

# Caractères que le cp1252 ne sait pas représenter : on translittère
# volontairement plutôt que de les perdre en silence.
TRANSLITTERATION = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
    " ": " ", "‑": "-",
}


class ErreurDeFormat(SystemExit):
    """Arrête proprement avec un message destiné à un humain, pas une trace."""

    def __init__(self, message: str):
        super().__init__(f"\n  {message}\n")


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

def decoder(chemin: Path) -> tuple[str, str]:
    """Renvoie (texte, encodage retenu). Ne lève jamais d'exception brute."""
    try:
        brut = chemin.read_bytes()
    except FileNotFoundError:
        raise ErreurDeFormat(f"Fichier introuvable : {chemin}")
    except IsADirectoryError:
        raise ErreurDeFormat(f"{chemin} est un dossier, pas un fichier.")
    except OSError as e:
        raise ErreurDeFormat(f"Impossible de lire {chemin} : {e}")

    if b"\x00" in brut[:4096]:
        raise ErreurDeFormat(
            f"{chemin.name} est un fichier binaire (PDF, image, tableur ?), "
            "pas un export texte. Attendu : le CSV telecharge depuis l'e-banking UBS."
        )

    if brut.startswith(BOM_UTF8):
        return brut.decode("utf-8-sig"), "UTF-8 avec BOM"
    for enc, nom in ENCODAGES_ESSAYES:
        try:
            texte = brut.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == "utf-8" and not any(b > 127 for b in brut):
            nom = "ASCII"
        return texte, nom
    return brut.decode("latin-1", errors="replace"), "indetermine (lu avec pertes)"


def lire_export(chemin: Path) -> tuple[dict[str, str], list[list[str]], str]:
    """Renvoie (métadonnées d'en-tête, lignes de la table, encodage source).

    On lit avec le module csv en lui passant un flux, jamais une liste de
    lignes découpée à l'avance : 1754 champs de ce fichier contiennent un
    « ; » entre guillemets, et certains contiennent un retour à la ligne.
    Découper d'abord souderait les mots de part et d'autre du retour.
    """
    texte, encodage = decoder(chemin)
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=SEPARATEUR))

    try:
        i_entete = next(i for i, r in enumerate(lignes) if r and r[0] == COL_ENTETE)
    except StopIteration:
        raise ErreurDeFormat(
            f"{chemin.name} : en-tete « {COL_ENTETE} » introuvable.\n"
            f"  Ce fichier n'est pas un export UBS e-banking (encodage lu : {encodage}).\n"
            "  Lancez diagnostic.py dessus pour savoir de quel format il s'agit."
        )

    meta = {r[0].rstrip(":"): r[1] for r in lignes[:i_entete] if len(r) > 1 and r[0]}
    table = []
    for numero, r in enumerate(lignes[i_entete + 1:], start=i_entete + 2):
        if not r or not any(c.strip() for c in r):
            continue
        if len(r) < COLONNES_REQUISES:
            raise ErreurDeFormat(
                f"{chemin.name}, ligne {numero} : {len(r)} colonne(s) au lieu de "
                f"{COLONNES_REQUISES} minimum.\n"
                f"  Contenu : {SEPARATEUR.join(r)[:90]}\n"
                "  Un pied de page ou une ligne de total s'est glisse dans la table."
            )
        table.append(r)
    return meta, table, encodage


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
            raise ErreurDeFormat(
                "Sous-ligne orpheline en tete de table : la premiere ligne de "
                "donnees n'a pas de date. Format inattendu."
            )
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
        except (ValueError, IndexError):
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
        except (ValueError, IndexError):
            anomalies.append(f"{mere[C_DATE_TRANS]} : sous-montant illisible")
            continue
        if abs(abs(total) - montant) > 0.005:
            anomalies.append(
                f"{mere[C_DATE_TRANS]} {mere[C_DESC1][:40]} : "
                f"somme des sous-montants {total:.2f} != montant mere {montant:.2f}"
            )
    return anomalies


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def assainir(texte: str, longueur_max: int) -> tuple[str, str | None]:
    """Prépare un texte pour le cp1252. Renvoie (texte, remarque éventuelle).

    Le séparateur est retiré du contenu, jamais échappé par des guillemets.
    Le module csv sait produire "champ;avec;separateur" selon la RFC 4180,
    mais rien ne garantit qu'un importateur métier ancien sache le relire :
    beaucoup découpent bêtement sur « ; ». Un champ échappé devient alors
    trois colonnes et l'import casse.

    Ce n'est pas théorique ici : 640 des 760 libellés UBS contiennent un
    « ; ». L'export Raiffeisen, lui, n'en contient aucun.
    """
    for source, cible in TRANSLITTERATION.items():
        texte = texte.replace(source, cible)
    texte = texte.replace(SEPARATEUR, ",").replace('"', "'")
    texte = " ".join(texte.split())  # absorbe aussi les retours a la ligne

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
    if longueur_max and len(resultat) > longueur_max:
        resultat = resultat[:longueur_max]
        remarque = (remarque + " ; " if remarque else "") + f"libelle tronque a {longueur_max}"
    return resultat, remarque


def convertir_date(iso: str) -> str:
    """2026-08-09 -> 09.08.2026"""
    a, m, j = iso.split("-")
    return f"{j}.{m}.{a}"


def construire_ecritures(groupes, longueur_libelle: int,
                         longueur_piece: int) -> tuple[list[Ecriture], int]:
    """Renvoie (écritures, nombre de lignes à 0.00 écartées)."""
    ecritures = []
    zero = 0
    for mere, sous in groupes:
        debit = mere[C_DEBIT].strip()
        credit = mere[C_CREDIT].strip()
        try:
            montant = float(debit or credit or 0)
        except ValueError:
            raise ErreurDeFormat(
                f"Montant illisible le {mere[C_DATE_TRANS]} : "
                f"debit={debit!r} credit={credit!r}"
            )

        if montant == 0:
            zero += 1  # lignes « Solde decompte des prix prestations » a 0.00
            continue

        # Le libellé utile : Description1, complété de Description2 quand
        # celle-ci porte le nom de la contrepartie plutôt qu'un code technique.
        parties = [mere[C_DESC1].strip()]
        desc2 = mere[C_DESC2].strip()
        if desc2 and not desc2.startswith(("20326812", "FILETRANSFER")):
            parties.append(desc2)
        libelle, remarque = assainir(" ".join(p for p in parties if p), longueur_libelle)
        remarques = [remarque] if remarque else []

        # Tronquer par la FIN, pas par le début : sur cet export les numéros
        # de transaction ne diffèrent que par leurs derniers caractères
        # (0104216DN2553368 vs 0104216DN2553365). Couper à gauche fabriquait
        # 12 collisions sur le fichier de référence.
        no_trans, _ = assainir(mere[C_NO_TRANS].strip(), 0)
        piece = no_trans[-longueur_piece:] if longueur_piece else no_trans
        if len(no_trans) > len(piece):
            remarques.append(f"numero de transaction tronque a {longueur_piece} caracteres")

        references = [
            s[C_DESC1].strip() for s in sous
            if len(s) > C_DESC1 and s[C_DESC1].strip().startswith("QRR:")
        ]

        date_source = mere[C_DATE_COMPTA].strip() or mere[C_DATE_TRANS].strip()
        if not mere[C_DATE_COMPTA].strip():
            remarques.append("date de comptabilisation absente : date de transaction utilisee")
        try:
            date = convertir_date(date_source)
        except ValueError:
            raise ErreurDeFormat(f"Date illisible : {date_source!r}")

        remarques.append("IMPUTER : contrepartie a determiner")

        ecritures.append(Ecriture(
            date=date, piece=piece, libelle=libelle, montant=abs(montant),
            sens="debit_banque" if credit else "credit_banque",
            references=references, remarques=remarques,
        ))
    return ecritures, zero


def desambiguer_pieces(ecritures, longueur_piece: int) -> list[str]:
    """Rend chaque numéro de pièce unique, de façon déterministe.

    UBS réutilise un même numéro de transaction pour un virement et ses
    « Frais de tiers » : 3 cas dans le fichier de référence. La collision
    vient donc de la source, pas de la troncature. On suffixe les doublons
    plutôt que de les laisser passer : un numéro de pièce partagé empêche de
    retrouver une écriture et casse toute reprise après un import partiel.
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
        budget = max(1, longueur_piece - len(suffixe)) if longueur_piece else len(base)
        e.piece = base[-budget:] + suffixe
        e.remarques.append(f"numero de piece '{base}' deja utilise, suffixe en '{e.piece}'")
        remarques.append(
            f"{e.date} {e.montant:>10.2f} {e.libelle[:35]} : "
            f"numero UBS '{base}' partage, renomme '{e.piece}'"
        )
    return remarques


def construire_lignes(ecritures, compte_banque, compte_attente, journal) -> list[list[str]]:
    """Fabrique et VALIDE toutes les lignes avant qu'un octet ne soit écrit.

    Sens comptable :
      - encaissement  -> débit banque   / crédit compte d'attente
      - décaissement  -> débit attente  / crédit banque
    Le montant est toujours positif : le sens est porté par les comptes.
    """
    lignes = []
    for e in ecritures:
        if e.sens == "debit_banque":
            cpt_debit, cpt_credit = compte_banque, compte_attente
        else:
            cpt_debit, cpt_credit = compte_attente, compte_banque
        ligne = [e.date, e.piece, cpt_debit, cpt_credit,
                 e.libelle, f"{e.montant:.2f}", journal]
        for i, champ in enumerate(ligne):
            champ = str(champ)
            if SEPARATEUR in champ or '"' in champ or "\n" in champ or "\r" in champ:
                raise ErreurDeFormat(
                    f"Bug interne : le champ {COLONNES_WINBIZ[i]} vaut {champ!r} et "
                    "contient un separateur, un guillemet ou un retour a la ligne.\n"
                    "  Aucun fichier n'a ete ecrit. Corriger assainir() avant d'importer."
                )
        lignes.append(ligne)
    return lignes


def ecrire_winbiz(lignes, chemin, entete):
    """Écrit le fichier. Toutes les lignes ont déjà été validées."""
    with open(chemin, "w", encoding=SORTIE_ENCODAGE, newline="") as f:
        w = csv.writer(f, delimiter=SEPARATEUR, lineterminator=SORTIE_FIN_LIGNE,
                       quoting=csv.QUOTE_NONE, quotechar=None)
        if entete:
            w.writerow(COLONNES_WINBIZ)
        w.writerows(lignes)


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def ecrire_rapport(chemin, source, meta, encodage, ecritures, anomalies_solde,
                   anomalies_sous, groupes, zero, remarques_piece, limite):
    def etat(anomalies, applicable):
        if not applicable:
            return "SANS OBJET (aucune donnee)"
        return "OK" if not anomalies else f"{len(anomalies)} ANOMALIE(S)"

    applicable = bool(groupes)
    lignes = [
        "RAPPORT DE CONVERSION UBS -> WINBIZ",
        "=" * 70,
        f"Fichier source : {source.name}",
        f"Encodage lu    : {encodage}",
        f"Compte         : {meta.get('IBAN', 'inconnu')}",
        f"Solde final    : {meta.get('Solde final', 'inconnu')}",
        "",
    ]

    if limite:
        lignes += [
            "*" * 70,
            f"*  FICHIER DE TEST : limite a {limite} ecriture(s).",
            "*  Les totaux ci-dessous ne reconstituent PAS le solde du compte.",
            "*  Ne pas utiliser pour un import de production.",
            "*" * 70,
            "",
        ]

    if not ecritures:
        lignes += [
            "!" * 70,
            "!  AUCUNE ECRITURE PRODUITE.",
            "!  Le fichier de sortie est vide. Verifiez le filtre de dates,",
            "!  la limite, ou le contenu du fichier source.",
            "!" * 70,
            "",
        ]

    lignes += [
        "CONTROLES",
        "-" * 70,
        f"  Transactions lues                  : {len(groupes)}",
        f"  Ecritures produites                : {len(ecritures)}",
        f"  Lignes a 0.00 ecartees             : {zero}",
        f"  Versements collectifs regroupes    : {sum(1 for _, s in groupes if s)}",
        f"  Chaine des soldes                  : {etat(anomalies_solde, applicable)}",
        f"  Coherence des sous-montants        : {etat(anomalies_sous, applicable)}",
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
    if not limite and ecritures:
        lignes += [
            "  La variation nette doit egaler solde final - solde initial du releve.",
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

    # Les remarques sont regroupees : une remarque qui touche toutes les
    # ecritures n'apprend rien ligne par ligne et noie les cas isoles.
    familles: dict[str, list[Ecriture]] = {}
    for e in ecritures:
        for r in e.remarques:
            if r.startswith("IMPUTER"):
                continue
            familles.setdefault(r.split(" : ")[0].split(" '")[0], []).append(e)
    if familles:
        lignes += ["REMARQUES DE TRANSFORMATION", "-" * 70]
        for famille, concernees in sorted(familles.items(), key=lambda kv: -len(kv[1])):
            part = f"{len(concernees)}/{len(ecritures)}"
            lignes.append(f"  {famille} — {part} ecriture(s)")
            if len(concernees) <= 5:
                for e in concernees:
                    lignes.append(f"      {e.date} {e.piece}")
        lignes.append("")

    Path(chemin).write_text("\n".join(lignes) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------

def date_iso(valeur: str) -> str:
    try:
        return datetime.strptime(valeur, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"« {valeur} » n'est pas une date AAAA-MM-JJ (exemple : 2026-07-01)"
        )


def entier_positif(valeur: str) -> int:
    try:
        n = int(valeur)
    except ValueError:
        raise argparse.ArgumentTypeError(f"« {valeur} » n'est pas un nombre entier")
    if n < 0:
        raise argparse.ArgumentTypeError(
            f"« {valeur} » est negatif. Utilisez 0 pour tout traiter."
        )
    return n


def longueur_piece_valide(valeur: str) -> int:
    n = entier_positif(valeur)
    if n and n < LONGUEUR_PIECE_MINIMALE:
        raise argparse.ArgumentTypeError(
            f"une longueur de piece de {n} ne distingue plus les ecritures ; "
            f"minimum {LONGUEUR_PIECE_MINIMALE}, ou 0 pour ne pas tronquer"
        )
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", type=Path, help="export UBS transactions(n).csv")
    p.add_argument("--compte-banque", default="1020", help="compte bancaire au plan comptable")
    p.add_argument("--compte-attente", default="9999", help="contrepartie provisoire")
    p.add_argument("--journal", default="", help="code journal WinBiz (colonne 7)")
    p.add_argument("--longueur-libelle", type=entier_positif, default=60)
    p.add_argument("--longueur-piece", type=longueur_piece_valide, default=15,
                   help="0 pour ne pas tronquer")
    p.add_argument("--limite", type=entier_positif, default=0, metavar="N",
                   help="ne produire que les N premieres ecritures (fichier de test)")
    p.add_argument("--depuis", type=date_iso, metavar="AAAA-MM-JJ")
    p.add_argument("--jusqua", type=date_iso, metavar="AAAA-MM-JJ")
    p.add_argument("--entete", action="store_true", help="ecrire la ligne d'en-tete")
    p.add_argument("-o", "--sortie", type=Path)
    args = p.parse_args()

    if args.depuis and args.jusqua and args.depuis > args.jusqua:
        raise ErreurDeFormat(
            f"--depuis {args.depuis} est posterieur a --jusqua {args.jusqua} : "
            "aucune transaction ne peut correspondre."
        )

    meta, table, encodage = lire_export(args.source)
    groupes = grouper(table)

    if args.depuis or args.jusqua:
        avant = len(groupes)
        groupes = [
            (m, sous) for m, sous in groupes
            if (not args.depuis or (m[C_DATE_COMPTA] or m[C_DATE_TRANS])[:10] >= args.depuis)
            and (not args.jusqua or (m[C_DATE_COMPTA] or m[C_DATE_TRANS])[:10] <= args.jusqua)
        ]
        print(f"filtre de dates : {len(groupes)} transactions retenues sur {avant}")

    anomalies_solde = controler_chaine_soldes(groupes)
    anomalies_sous = controler_sous_montants(groupes)

    ecritures, zero = construire_ecritures(groupes, args.longueur_libelle,
                                           args.longueur_piece)
    if args.limite:
        total = len(ecritures)
        ecritures = ecritures[:args.limite]
        print(f"FICHIER DE TEST : {len(ecritures)} ecritures sur {total}. "
              f"Les totaux ne reconstituent pas le solde du compte.")

    remarques_piece = desambiguer_pieces(ecritures, args.longueur_piece)

    # Tout est valide ici : rien n'a encore ete ecrit sur le disque.
    lignes = construire_lignes(ecritures, args.compte_banque,
                               args.compte_attente, args.journal)

    if args.sortie:
        sortie = args.sortie
    else:
        marque = "_TEST" if args.limite else ""
        sortie = args.source.with_name(args.source.stem + marque + "_winbiz.csv")
    rapport = sortie.with_name(sortie.stem + "_rapport.txt")

    ecrire_winbiz(lignes, sortie, args.entete)
    ecrire_rapport(rapport, args.source, meta, encodage, ecritures, anomalies_solde,
                   anomalies_sous, groupes, zero, remarques_piece, args.limite)

    print(f"{len(ecritures)} ecritures -> {sortie}")
    print(f"rapport -> {rapport}")

    if not ecritures:
        print("ATTENTION : aucune ecriture produite, le fichier est vide.",
              file=sys.stderr)
        return 1
    if anomalies_solde or anomalies_sous:
        print(f"ATTENTION : {len(anomalies_solde) + len(anomalies_sous)} anomalie(s), "
              "voir le rapport avant d'importer.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
