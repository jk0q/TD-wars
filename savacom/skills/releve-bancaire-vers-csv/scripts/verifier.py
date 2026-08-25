#!/usr/bin/env python3
"""
Vérifie qu'un relevé bancaire lu depuis un PDF ou une image se referme
arithmétiquement, puis — et seulement alors — écrit le CSV au format de la
banque.

Lire une image peut inventer un chiffre. Un relevé imprime ses propres
totaux : il porte sa propre preuve. Ce script recalcule et compare. Tant que
ça ne tombe pas juste, aucun CSV n'est écrit.

    python verifier.py controler releve.json
    python verifier.py ecrire releve.json --format formats/bcn.json -o sortie.csv

Code de sortie : 0 si tous les contrôles passent, 1 sinon.

FORMAT DU FICHIER DE LECTURE
----------------------------
    {
      "banque": "bcn",
      "iban": "CH17 0076 6000 1034 3068 1",
      "titulaire": "Voisin Serrurerie Sarl",
      "periode":  {"debut": "2026-08-01", "fin": "2026-08-31"},
      "pages":    {"lues": 3, "annoncees": 3},
      "totaux_imprimes": {
        "solde_initial": "110325.56",
        "solde_final":   "86515.90",
        "total_debits":  "23809.66",
        "total_credits": "0.00"
      },
      "lignes": [
        {
          "date":        "2026-08-03",
          "date_valeur": "2026-08-03",
          "libelle":     "Paiement facture 2026-114",
          "debit":       "1200.00",
          "credit":      null,
          "solde":       "109125.56",
          "confiance":   "sure",
          "note":        ""
        }
      ]
    }

Les montants s'écrivent en chiffres ou en texte, peu importe : ils sont lus
en decimal exact, jamais en flottant. Un montant absent vaut null.

« confiance » vaut "sure" ou "douteuse". Marquez "douteuse" tout chiffre mal
imprimé, coupé, ou ambigu, et dites pourquoi dans « note » : le contrôle
bloquera dessus, ce qui est exactement le but. Deviner pour finir proprement
est le seul vrai échec possible.

Les lignes sont dans l'ordre du relevé, tel qu'imprimé. Le sens
chronologique est déduit, pas supposé.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

TOLERANCE = Decimal("0.005")  # un demi-centime : le relevé peut arrondir
CHAMPS_LIGNE = ("date", "date_valeur", "libelle", "debit", "credit", "solde")


class ErreurDeFormat(SystemExit):
    """Sortie lisible par un humain, jamais une trace d'exception."""

    def __init__(self, message: str):
        super().__init__(f"\n  {message}\n")


# ---------------------------------------------------------------------------
# Lecture du fichier de relevé
# ---------------------------------------------------------------------------

def montant(valeur, ou: str) -> Decimal | None:
    """Convertit en décimal exact. Renvoie None pour une case vide."""
    if valeur is None or valeur == "":
        return None
    try:
        return Decimal(str(valeur).replace("'", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ErreurDeFormat(f"{ou} : montant illisible {valeur!r}")


def date_iso(valeur, ou: str):
    if valeur is None or valeur == "":
        return None
    try:
        return datetime.strptime(str(valeur), "%Y-%m-%d").date()
    except ValueError:
        raise ErreurDeFormat(
            f"{ou} : date {valeur!r} attendue au format AAAA-MM-JJ "
            "(exemple : 2026-08-03)"
        )


def charger(chemin: Path) -> dict:
    try:
        brut = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ErreurDeFormat(f"Fichier introuvable : {chemin}")
    except OSError as e:
        raise ErreurDeFormat(f"Impossible de lire {chemin} : {e}")
    try:
        releve = json.loads(brut)
    except json.JSONDecodeError as e:
        raise ErreurDeFormat(
            f"{chemin.name} n'est pas du JSON valide : {e.msg} "
            f"(ligne {e.lineno}, colonne {e.colno})"
        )
    if not isinstance(releve, dict):
        raise ErreurDeFormat(f"{chemin.name} : un objet JSON est attendu.")

    lignes = releve.get("lignes")
    if not isinstance(lignes, list) or not lignes:
        raise ErreurDeFormat(
            f"{chemin.name} : aucune ligne. Le relevé doit contenir « lignes », "
            "une liste non vide."
        )

    for i, l in enumerate(lignes, start=1):
        if not isinstance(l, dict):
            raise ErreurDeFormat(f"Ligne {i} : un objet est attendu, pas {type(l).__name__}.")
        ou = f"ligne {i}"
        l["_i"] = i
        l["_date"] = date_iso(l.get("date"), ou)
        l["_date_valeur"] = date_iso(l.get("date_valeur"), ou)
        l["_debit"] = montant(l.get("debit"), ou + " (debit)")
        l["_credit"] = montant(l.get("credit"), ou + " (credit)")
        l["_solde"] = montant(l.get("solde"), ou + " (solde)")
        if l["_debit"] is not None and l["_credit"] is not None:
            raise ErreurDeFormat(
                f"Ligne {i} : debit ET credit renseignes. "
                "Une transaction va dans un sens ou dans l'autre, pas les deux."
            )
        if l["_debit"] is None and l["_credit"] is None:
            raise ErreurDeFormat(
                f"Ligne {i} : ni debit ni credit. Si la ligne n'est pas une "
                "transaction (report, sous-total), ne la relevez pas."
            )

    totaux = releve.get("totaux_imprimes") or {}
    for cle in ("solde_initial", "solde_final", "total_debits", "total_credits"):
        releve.setdefault("_totaux", {})[cle] = montant(totaux.get(cle), f"totaux_imprimes.{cle}")
    return releve


# ---------------------------------------------------------------------------
# Contrôles
# ---------------------------------------------------------------------------

def somme(lignes, champ) -> Decimal:
    return sum((l[champ] for l in lignes if l[champ] is not None), Decimal("0"))


def ecart(a: Decimal, b: Decimal) -> Decimal:
    return abs(a - b)


def chaine_soldes(lignes) -> tuple[str, list[str]]:
    """Éprouve les deux sens de lecture et retient celui qui tient.

    Un relevé peut être imprimé du plus ancien au plus récent ou l'inverse.
    Plutôt que de le supposer, on teste les deux et on garde le sens qui
    produit le moins de ruptures — puis on le dit.
    """
    avec_solde = [l for l in lignes if l["_solde"] is not None]
    if len(avec_solde) < 2:
        return "indeterminable", []

    def mouvement(l) -> Decimal:
        return (l["_credit"] or Decimal("0")) - (l["_debit"] or Decimal("0"))

    def ruptures(anti: bool) -> list[str]:
        sorties = []
        for a, b in zip(avec_solde, avec_solde[1:]):
            if anti:
                # a est plus recent que b : solde(a) = solde(b) + mouvement de a
                attendu, constate, ligne = b["_solde"] + mouvement(a), a["_solde"], a
            else:
                # a est plus ancien que b : solde(b) = solde(a) + mouvement de b
                attendu, constate, ligne = a["_solde"] + mouvement(b), b["_solde"], b
            if ecart(attendu, constate) > TOLERANCE:
                sorties.append(
                    f"ligne {ligne['_i']} ({ligne.get('date')}) : solde {constate} "
                    f"au lieu de {attendu} attendu — ecart {ecart(attendu, constate)}"
                )
        return sorties

    anti = ruptures(True)
    chrono = ruptures(False)
    if len(anti) <= len(chrono):
        return "anti_chronologique", anti
    return "chronologique", chrono


def controler(releve: dict) -> tuple[list[str], list[str], dict]:
    """Renvoie (anomalies bloquantes, avertissements, mesures)."""
    lignes = releve["lignes"]
    t = releve["_totaux"]
    anomalies, avertissements = [], []

    debits, credits = somme(lignes, "_debit"), somme(lignes, "_credit")
    mesures = {
        "lignes": len(lignes),
        "debits_lus": debits,
        "credits_lus": credits,
        "variation": credits - debits,
    }

    # 1. Pages — un scan tronque est le defaut le plus frequent et le plus muet.
    pages = releve.get("pages") or {}
    lues, annoncees = pages.get("lues"), pages.get("annoncees")
    if lues is None or annoncees is None:
        avertissements.append(
            "nombre de pages non releve : impossible de garantir que le releve est complet"
        )
    elif lues != annoncees:
        anomalies.append(f"{lues} page(s) lue(s) sur {annoncees} annoncee(s) — releve incomplet")
    mesures["pages"] = f"{lues}/{annoncees}" if lues is not None else "non releve"

    # 2. Lectures douteuses — un humain doit les regarder avant tout le reste.
    douteuses = [l for l in lignes if str(l.get("confiance", "sure")).lower() != "sure"]
    for l in douteuses:
        note = l.get("note") or "aucune precision"
        anomalies.append(f"ligne {l['_i']} ({l.get('date')}) marquee douteuse : {note}")

    # 3. Totaux imprimes.
    if t["total_debits"] is not None:
        e = ecart(debits, t["total_debits"])
        if e > TOLERANCE:
            anomalies.append(
                f"debits : {debits} lus contre {t['total_debits']} imprimes — ecart {e}"
            )
    else:
        avertissements.append("total des debits non releve sur le document")

    if t["total_credits"] is not None:
        e = ecart(credits, t["total_credits"])
        if e > TOLERANCE:
            anomalies.append(
                f"credits : {credits} lus contre {t['total_credits']} imprimes — ecart {e}"
            )
    else:
        avertissements.append("total des credits non releve sur le document")

    # 4. Le releve dans son ensemble : solde initial - debits + credits = solde final.
    if t["solde_initial"] is not None and t["solde_final"] is not None:
        attendu = t["solde_initial"] - debits + credits
        e = ecart(attendu, t["solde_final"])
        mesures["solde_reconstitue"] = attendu
        if e > TOLERANCE:
            anomalies.append(
                f"solde final : {attendu} reconstitue contre {t['solde_final']} "
                f"imprime — ecart {e}"
            )
    else:
        avertissements.append("soldes initial/final non releves : reconstitution impossible")

    # 5. Chaine des soldes ligne a ligne.
    sens, ruptures = chaine_soldes(lignes)
    mesures["sens"] = sens
    if sens == "indeterminable":
        avertissements.append("soldes par ligne absents : chaine des soldes non verifiable")
    else:
        anomalies.extend("chaine des soldes — " + r for r in ruptures)

    # 6. Dates dans la periode annoncee.
    periode = releve.get("periode") or {}
    debut = date_iso(periode.get("debut"), "periode.debut")
    fin = date_iso(periode.get("fin"), "periode.fin")
    if debut and fin:
        if debut > fin:
            anomalies.append(f"periode incoherente : {debut} apres {fin}")
        hors = [l for l in lignes if l["_date"] and not (debut <= l["_date"] <= fin)]
        for l in hors[:5]:
            anomalies.append(f"ligne {l['_i']} : date {l['_date']} hors periode {debut} — {fin}")
        if len(hors) > 5:
            anomalies.append(f"... et {len(hors) - 5} autre(s) date(s) hors periode")
        mesures["periode"] = f"{debut} — {fin}"
    else:
        avertissements.append("periode du releve non relevee")

    # 7. Doublons exacts — legitimes parfois, a confirmer toujours.
    vus = {}
    for l in lignes:
        cle = (l.get("date"), str(l.get("libelle", "")).strip(), l["_debit"], l["_credit"])
        vus.setdefault(cle, []).append(l["_i"])
    for cle, indices in vus.items():
        if len(indices) > 1:
            avertissements.append(
                f"lignes {', '.join(map(str, indices))} identiques "
                f"({cle[0]}, {cle[1][:40]}) — a confirmer sur le document"
            )

    return anomalies, avertissements, mesures


def afficher_rapport(releve, anomalies, avertissements, mesures) -> None:
    print("=" * 72)
    print(f"  CONTROLE DU RELEVE — {releve.get('banque', 'banque non precisee').upper()}")
    print("=" * 72)
    if releve.get("iban"):
        print(f"  Compte           : {releve['iban']}")
    if releve.get("titulaire"):
        print(f"  Titulaire        : {releve['titulaire']}")
    print(f"  Periode          : {mesures.get('periode', 'non relevee')}")
    print(f"  Pages            : {mesures['pages']}")
    print(f"  Lignes lues      : {mesures['lignes']}")
    print(f"  Sens de lecture  : {mesures['sens']}")
    print()
    print(f"  Total des debits : {mesures['debits_lus']:>14}")
    print(f"  Total des credits: {mesures['credits_lus']:>14}")
    print(f"  Variation nette  : {mesures['variation']:>14}")
    if "solde_reconstitue" in mesures:
        print(f"  Solde reconstitue: {mesures['solde_reconstitue']:>14}")
    print()

    if anomalies:
        print("  ANOMALIES BLOQUANTES")
        print("  " + "-" * 68)
        for a in anomalies:
            print(f"    {a}")
        print()
        print("  Aucun CSV ne sera ecrit. Relisez les lignes nommees sur le")
        print("  document : l'ecart au centime suffit presque toujours a")
        print("  retrouver le chiffre mal lu.")
        print()
    else:
        print("  Tous les controles passent.")
        print()

    if avertissements:
        print("  AVERTISSEMENTS")
        print("  " + "-" * 68)
        for a in avertissements:
            print(f"    {a}")
        print()


# ---------------------------------------------------------------------------
# Écriture du CSV
# ---------------------------------------------------------------------------

def formater_montant(valeur: Decimal | None, spec: dict) -> str:
    if valeur is None:
        return ""
    q = Decimal(1).scaleb(-int(spec.get("decimales", 2)))
    texte = f"{valeur.quantize(q):f}"
    negatif = texte.startswith("-")
    texte = texte.lstrip("-")
    entier, _, dec = texte.partition(".")
    milliers = spec.get("separateur_milliers", "aucun")
    if milliers and milliers != "aucun":
        morceaux = []
        while len(entier) > 3:
            morceaux.insert(0, entier[-3:])
            entier = entier[:-3]
        morceaux.insert(0, entier)
        entier = milliers.join(morceaux)
    sortie = entier + (spec.get("separateur_decimal", ".") + dec if dec else "")
    return ("-" if negatif else "") + sortie


def valeur_colonne(ligne: dict, specification: str, fmt: dict) -> str:
    if specification == "vide":
        return ""
    if specification.startswith("constante:"):
        return specification.split(":", 1)[1]
    if specification in ("date", "date_valeur"):
        d = ligne["_" + specification]
        return d.strftime(fmt["format_date"]) if d else ""
    if specification == "libelle":
        return str(ligne.get("libelle") or "")
    if specification == "montant":
        m = (ligne["_credit"] or Decimal("0")) - (ligne["_debit"] or Decimal("0"))
        return formater_montant(m, fmt["format_montant"])
    if specification in ("debit", "credit", "solde"):
        v = ligne["_" + specification]
        if specification == "debit" and v is not None and fmt["format_montant"].get("debit_negatif"):
            v = -v
        return formater_montant(v, fmt["format_montant"])
    raise ErreurDeFormat(
        f"Le format demande une colonne « {specification} », inconnue. "
        f"Attendu : {', '.join(CHAMPS_LIGNE)}, montant, vide, ou constante:XXX."
    )


def charger_format(chemin: Path) -> dict:
    fmt = json.loads(chemin.read_text(encoding="utf-8"))
    if fmt.get("statut") != "mesure":
        raise ErreurDeFormat(
            f"{chemin.name} porte statut « {fmt.get('statut')} » : ce format n'a "
            "pas encore ete mesure sur un vrai export de la banque.\n"
            "  Ecrire un CSV maintenant reviendrait a deviner des colonnes, et il\n"
            "  serait refuse a l'import. Demandez a l'utilisateur un export CSV\n"
            "  reel de cette banque, passez-le a diagnostic.py, et completez le\n"
            "  fichier de format en suivant _MODELE.json."
        )
    for cle in ("encodage", "fin_de_ligne", "separateur", "entete", "colonnes",
                "format_date", "format_montant", "ordre"):
        if not fmt.get(cle):
            raise ErreurDeFormat(f"{chemin.name} : champ « {cle} » manquant ou vide.")
    if len(fmt["colonnes"]) != len(fmt["entete"]):
        raise ErreurDeFormat(
            f"{chemin.name} : {len(fmt['colonnes'])} colonne(s) decrite(s) pour "
            f"{len(fmt['entete'])} en-tete(s). Les deux listes doivent correspondre."
        )
    return fmt


def ecrire(releve: dict, fmt: dict, sortie: Path) -> int:
    lignes = list(releve["lignes"])
    datees = [l for l in lignes if l["_date"]]
    if len(datees) == len(lignes):
        lignes.sort(key=lambda l: l["_date"], reverse=fmt["ordre"] == "anti_chronologique")

    rangs = [[valeur_colonne(l, c, fmt) for c in fmt["colonnes"]] for l in lignes]

    if fmt.get("guillemets") == "jamais":
        sep = fmt["separateur"]
        rangs = [[c.replace(sep, ",") for c in r] for r in rangs]
        quoting = csv.QUOTE_NONE
    else:
        quoting = csv.QUOTE_MINIMAL

    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=fmt["separateur"],
                          lineterminator=fmt["fin_de_ligne"].replace("CRLF", "\r\n").replace("LF", "\n"),
                          quoting=quoting)
    # Chaque ligne de metadonnee est une liste de cellules, jamais du texte a
    # redecouper : une valeur contenant le separateur casserait le redecoupage.
    remplacements = {k: v for k, v in releve.items() if isinstance(v, (str, int))}
    for meta in fmt.get("lignes_avant_entete") or []:
        if isinstance(meta, str):
            raise ErreurDeFormat(
                "lignes_avant_entete : chaque ligne doit etre une liste de "
                f"cellules, pas une chaine. Recu : {meta!r}"
            )
        ecrivain.writerow([str(c).format(**remplacements) for c in meta])
    if fmt.get("ecrire_entete", True):
        ecrivain.writerow(fmt["entete"])
    ecrivain.writerows(rangs)

    texte = tampon.getvalue()
    try:
        octets = texte.encode(fmt["encodage"], errors="strict")
    except UnicodeEncodeError as e:
        fautif = texte[e.start:e.end]
        ligne = texte.count("\n", 0, e.start) + 1
        raise ErreurDeFormat(
            f"Le caractere {fautif!r} (ligne {ligne} du fichier a produire) "
            f"n'existe pas en {fmt['encodage']}, l'encodage de cette banque.\n"
            "  Sur un releve scanne, c'est presque toujours un caractere mal lu.\n"
            "  Relisez le libelle concerne sur le document plutot que de le\n"
            "  remplacer au jugé : le CSV n'a pas ete ecrit."
        )
    # Ecriture en un seul appel : une erreur en cours de route laisserait
    # sinon un fichier tronque a cote d'un rapport qui dit que tout va bien.
    sortie.write_bytes(octets)
    return len(rangs)


# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = p.add_subparsers(dest="action", required=True)

    c = sous.add_parser("controler", help="verifier sans rien ecrire")
    c.add_argument("releve", type=Path)

    e = sous.add_parser("ecrire", help="verifier puis ecrire le CSV")
    e.add_argument("releve", type=Path)
    e.add_argument("--format", type=Path, required=True, dest="fmt")
    e.add_argument("-o", "--sortie", type=Path, required=True)

    args = p.parse_args()
    releve = charger(args.releve)
    anomalies, avertissements, mesures = controler(releve)
    afficher_rapport(releve, anomalies, avertissements, mesures)

    if anomalies:
        return 1
    if args.action == "controler":
        return 0

    fmt = charger_format(args.fmt)
    n = ecrire(releve, fmt, args.sortie)
    print(f"  {n} ligne(s) ecrite(s) -> {args.sortie}")
    print(f"  Format {fmt['nom']} : {fmt['encodage']}, {fmt['fin_de_ligne']}, "
          f"separateur « {fmt['separateur']} »")
    print()
    print("  Ce fichier est une TRANSCRIPTION d'un document scanne, pas un")
    print("  export d'origine de la banque. Dites-le en le transmettant.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
