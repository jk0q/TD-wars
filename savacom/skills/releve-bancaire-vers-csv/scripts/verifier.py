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
import codecs
import csv
import io
import json
import sys
from datetime import date, datetime
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
        d = Decimal(str(valeur).replace("'", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ErreurDeFormat(f"{ou} : montant illisible {valeur!r}")
    if not d.is_finite():
        # « NaN » et « Infinity » sont des decimaux valides pour Python et
        # feraient exploser la premiere comparaison, apres tous les controles.
        raise ErreurDeFormat(f"{ou} : {valeur!r} n'est pas un nombre exploitable")
    return d


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
        if not str(l.get("date") or "").strip():
            raise ErreurDeFormat(
                f"Ligne {i} : pas de date.\n"
                "  Une transaction sans date ne peut etre ni situee dans la periode,\n"
                "  ni ordonnee dans le fichier de sortie. Relisez-la sur le document ;\n"
                "  si c'est une sous-ligne d'un versement collectif, ne la relevez pas\n"
                "  comme une transaction."
            )
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


def mouvement(l) -> Decimal:
    """Ce que la ligne ajoute au solde : positif en credit, negatif en debit."""
    return (l["_credit"] or Decimal("0")) - (l["_debit"] or Decimal("0"))


def chaine_soldes(lignes) -> tuple[str, list[str]]:
    """Éprouve les deux sens de lecture et retient celui qui tient.

    Un relevé peut être imprimé du plus ancien au plus récent ou l'inverse.
    Plutôt que de le supposer, on teste les deux et on garde le sens qui
    produit le moins de ruptures — puis on le dit.

    Beaucoup de relevés n'impriment un solde que sur certaines lignes. Entre
    deux soldes imprimés il faut donc cumuler les mouvements de TOUTES les
    lignes intermédiaires, pas seulement celui de la ligne portant le solde.
    Ne pas le faire fabriquait une fausse rupture bloquante sur des relevés
    parfaitement justes, et envoyait relire une ligne qui n'avait rien.

    En lecture chronologique (la plus ancienne d'abord) :
        solde(b) = solde(a) + somme des mouvements de a+1 a b
    En lecture anti-chronologique (la plus recente d'abord) :
        solde(a) = solde(b) + somme des mouvements de a a b-1
    """
    positions = [i for i, l in enumerate(lignes) if l["_solde"] is not None]
    if len(positions) < 2:
        return "indeterminable", []

    def ruptures(anti: bool) -> list[str]:
        sorties = []
        for ia, ib in zip(positions, positions[1:]):
            a, b = lignes[ia], lignes[ib]
            if anti:
                cumul = sum((mouvement(l) for l in lignes[ia:ib]), Decimal("0"))
                attendu, constate, ligne = b["_solde"] + cumul, a["_solde"], a
            else:
                cumul = sum((mouvement(l) for l in lignes[ia + 1:ib + 1]), Decimal("0"))
                attendu, constate, ligne = a["_solde"] + cumul, b["_solde"], b
            if ecart(attendu, constate) > TOLERANCE:
                sorties.append(
                    f"ligne {ligne['_i']} ({ligne.get('date')}) : solde {constate} "
                    f"au lieu de {attendu} attendu — ecart {ecart(attendu, constate)}"
                )
        return sorties

    anti = ruptures(True)
    chrono = ruptures(False)
    if not anti and chrono:
        return "anti_chronologique", []
    if not chrono and anti:
        return "chronologique", []
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
    banque = str(releve.get("banque") or "banque non precisee").upper()
    print(f"  CONTROLE DU RELEVE — {banque}")
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
#
# Tout ce qui suit part d'un fichier de format ECRIT A LA MAIN, en recopiant la
# sortie de diagnostic.py. C'est donc une source d'erreurs humaines, et chaque
# valeur est validee avant que le premier octet ne soit produit. Sans cette
# validation, une valeur recopiee de travers — « CRLF (Windows) » au lieu de
# « CRLF » — passait dans le fichier de sortie sans un mot, et le CSV etait
# faux avec « Tous les controles passent » a l'ecran.

FINS_DE_LIGNE = {"CRLF": "\r\n", "LF": "\n"}
MILLIERS = {"aucun": "", "'": "'", "espace": " "}
SEPARATEURS_DECIMAUX = {".", ","}
GUILLEMETS_ADMIS = {"jamais", "si_necessaire"}
ORDRES_ADMIS = {"chronologique", "anti_chronologique"}
CHAMPS_COLONNE = set(CHAMPS_LIGNE) | {"montant", "vide"}


def formater_montant(valeur: Decimal | None, spec: dict) -> str:
    if valeur is None:
        return ""
    q = Decimal(1).scaleb(-spec["decimales"])
    texte = f"{valeur.quantize(q):f}"
    negatif = texte.startswith("-")
    entier, _, dec = texte.lstrip("-").partition(".")
    milliers = MILLIERS[spec["separateur_milliers"]]
    if milliers:
        morceaux = []
        while len(entier) > 3:
            morceaux.insert(0, entier[-3:])
            entier = entier[:-3]
        morceaux.insert(0, entier)
        entier = milliers.join(morceaux)
    sortie = entier + (spec["separateur_decimal"] + dec if dec else "")
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
        # Une colonne signee unique porte deja son sens : le credit est positif,
        # le debit negatif. debit_negatif ne la concerne pas.
        return formater_montant(mouvement(ligne), fmt["format_montant"])
    v = ligne["_" + specification]
    if specification == "debit" and v is not None and fmt["format_montant"]["debit_negatif"]:
        v = -v
    return formater_montant(v, fmt["format_montant"])


def _exiger(condition, message: str) -> None:
    if not condition:
        raise ErreurDeFormat(message)


def charger_format(chemin: Path) -> dict:
    """Charge et VALIDE un fichier de format. Rien n'est ecrit avant ce passage."""
    try:
        fmt = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErreurDeFormat(f"Fichier de format introuvable : {chemin}")
    except OSError as e:
        raise ErreurDeFormat(f"Impossible de lire {chemin} : {e}")
    except json.JSONDecodeError as e:
        raise ErreurDeFormat(
            f"{chemin.name} n'est pas du JSON valide : {e.msg} "
            f"(ligne {e.lineno}, colonne {e.colno})"
        )
    _exiger(isinstance(fmt, dict), f"{chemin.name} : un objet JSON est attendu.")

    if fmt.get("statut") != "mesure":
        raise ErreurDeFormat(
            f"{chemin.name} porte statut « {fmt.get('statut')} » : ce format n'a "
            "pas encore ete mesure sur un vrai export de la banque.\n"
            "  Ecrire un CSV maintenant reviendrait a deviner des colonnes, et il\n"
            "  serait refuse a l'import. Demandez a l'utilisateur un export CSV\n"
            "  reel de cette banque, passez-le a diagnostic.py, et completez le\n"
            "  fichier de format en suivant _MODELE.json."
        )

    ou = chemin.name
    _exiger(isinstance(fmt.get("nom"), str) and fmt["nom"].strip(),
            f"{ou} : « nom » manquant — le nom affiche de la banque.")

    enc = fmt.get("encodage")
    _exiger(isinstance(enc, str) and enc, f"{ou} : « encodage » manquant.")
    try:
        codecs.lookup(enc)
    except LookupError:
        raise ErreurDeFormat(
            f"{ou} : « {enc} » n'est pas un encodage connu.\n"
            "  Attendu un nom technique — utf-8, utf-8-sig, cp1252, latin-1 —\n"
            "  et non le libelle affiche par diagnostic.py."
        )

    fdl = fmt.get("fin_de_ligne")
    _exiger(fdl in FINS_DE_LIGNE,
            f"{ou} : « fin_de_ligne » vaut {fdl!r}, attendu « CRLF » ou « LF » "
            "exactement, sans commentaire.")

    sep = fmt.get("separateur")
    _exiger(isinstance(sep, str) and len(sep) == 1,
            f"{ou} : « separateur » doit etre un seul caractere, recu {sep!r}.")

    ordre = fmt.get("ordre")
    _exiger(ordre in ORDRES_ADMIS,
            f"{ou} : « ordre » vaut {ordre!r}, attendu « chronologique » ou "
            "« anti_chronologique ». Cette valeur decide de l'ordre de TOUTES les "
            "lignes du fichier : elle se mesure sur un vrai export, elle ne se "
            "laisse pas a « inconnu ».")

    guillemets = fmt.setdefault("guillemets", "si_necessaire")
    _exiger(guillemets in GUILLEMETS_ADMIS,
            f"{ou} : « guillemets » vaut {guillemets!r}, attendu "
            f"{' ou '.join(sorted(GUILLEMETS_ADMIS))}.")

    _exiger(isinstance(fmt.get("ecrire_entete", True), bool),
            f"{ou} : « ecrire_entete » doit valoir true ou false.")

    entete, colonnes = fmt.get("entete"), fmt.get("colonnes")
    _exiger(isinstance(entete, list) and entete and all(isinstance(c, str) for c in entete),
            f"{ou} : « entete » doit etre la liste non vide des noms de colonnes.")
    _exiger(isinstance(colonnes, list) and all(isinstance(c, str) for c in colonnes),
            f"{ou} : « colonnes » doit etre une liste de chaines.")
    _exiger(len(colonnes) == len(entete),
            f"{ou} : {len(colonnes)} colonne(s) decrite(s) pour {len(entete)} "
            "en-tete(s). Les deux listes doivent correspondre une pour une.")
    for i, c in enumerate(colonnes):
        _exiger(c in CHAMPS_COLONNE or c.startswith("constante:"),
                f"{ou} : colonne {i} vaut {c!r}, inconnu.\n"
                f"  Attendu : {', '.join(sorted(CHAMPS_COLONNE))}, ou constante:XXX.")

    # Champ informatif, mais un desaccord avec « colonnes » signale un fichier
    # de format rempli sans relire : autant le dire tout de suite.
    une_colonne = fmt.get("montant_en_une_colonne")
    if isinstance(une_colonne, bool):
        constate = "montant" in colonnes
        _exiger(une_colonne == constate,
                f"{ou} : « montant_en_une_colonne » vaut {une_colonne}, mais "
                f"« colonnes » {'contient' if constate else 'ne contient pas'} "
                "« montant ». Les deux doivent s'accorder.")

    fd = fmt.get("format_date")
    _exiger(isinstance(fd, str) and fd, f"{ou} : « format_date » manquant.")
    # Trois epreuves, parce qu'aucune ne suffit seule. Le gabarit de _MODELE.json
    # — « %d.%m.%Y | %Y-%m-%d | %d/%m/%y — tel qu'il apparait dans l'export » —
    # contient de vraies directives : il passe l'epreuve 1 et l'epreuve 3, et
    # remplirait chaque cellule date avec une phrase. Seule la longueur le voit.
    temoin = date(2026, 8, 3)
    try:
        rendu = temoin.strftime(fd)
        autre = date(2027, 12, 25).strftime(fd)
    except (ValueError, TypeError):
        raise ErreurDeFormat(f"{ou} : « format_date » {fd!r} est inutilisable.")

    gabarit = (f"{ou} : « format_date » {fd!r} n'est pas un format de date "
               "utilisable.\n  Une date du 3 aout 2026 y devient {rendu!r}.\n"
               "  Attendu quelque chose comme %d.%m.%Y ou %Y-%m-%d, seul, sans "
               "commentaire\n  ni liste de variantes — c'est vraisemblablement le "
               "texte d'exemple de\n  _MODELE.json, recopie tel quel.")
    _exiger(rendu != autre, gabarit.format(rendu=rendu))
    _exiger(len(rendu) <= 32, gabarit.format(rendu=rendu))
    try:
        relu = datetime.strptime(rendu, fd).date()
    except ValueError:
        raise ErreurDeFormat(gabarit.format(rendu=rendu))
    _exiger(relu == temoin, gabarit.format(rendu=rendu))

    fm = fmt.get("format_montant")
    _exiger(isinstance(fm, dict), f"{ou} : « format_montant » manquant.")
    _exiger(isinstance(fm.get("decimales"), int) and not isinstance(fm["decimales"], bool)
            and 0 <= fm["decimales"] <= 6,
            f"{ou} : « decimales » doit etre un entier de 0 a 6, recu "
            f"{fm.get('decimales')!r}.")
    _exiger(fm.get("separateur_decimal") in SEPARATEURS_DECIMAUX,
            f"{ou} : « separateur_decimal » vaut {fm.get('separateur_decimal')!r}, "
            "attendu « . » ou « , ».")
    _exiger(fm.get("separateur_milliers") in MILLIERS,
            f"{ou} : « separateur_milliers » vaut {fm.get('separateur_milliers')!r}, "
            f"attendu {', '.join(repr(k) for k in MILLIERS)}.")
    _exiger(isinstance(fm.get("debit_negatif"), bool),
            f"{ou} : « debit_negatif » doit valoir true ou false, recu "
            f"{fm.get('debit_negatif')!r}.")

    metas = fmt.get("lignes_avant_entete") or []
    _exiger(isinstance(metas, list), f"{ou} : « lignes_avant_entete » doit etre une liste.")
    for i, meta in enumerate(metas):
        _exiger(isinstance(meta, list) and all(isinstance(c, str) for c in meta),
                f"{ou} : lignes_avant_entete[{i}] doit etre une liste de cellules, "
                f"pas {type(meta).__name__}. Exemple : [\"IBAN:\", \"{{iban}}\"]")
    return fmt


def assainir(texte: str, sep: str) -> tuple[str, bool]:
    """Rend un texte ecrivable sans guillemets. Dit s'il a fallu le modifier."""
    propre = texte.replace(sep, ",").replace('"', "'")
    propre = " ".join(propre.split())  # absorbe retours a la ligne et tabulations
    return propre, propre != texte


def ecrire(releve: dict, fmt: dict, sortie: Path, sens: str) -> tuple[int, int]:
    """Renvoie (lignes ecrites, champs assainis)."""
    lignes = list(releve["lignes"])

    # L'ordre imprime du releve est connu quand la chaine des soldes a pu etre
    # eprouvee. Dans ce cas on RENVERSE la liste plutot que de la trier par
    # date : deux ecritures du meme jour gardent alors l'ordre du document.
    # Un tri par date seul ne les reordonnait jamais — le tri de Python est
    # stable — et produisait une colonne de soldes en desordre.
    if sens in ORDRES_ADMIS:
        if sens != fmt["ordre"]:
            lignes.reverse()
    else:
        lignes.sort(key=lambda l: l["_date"],
                    reverse=fmt["ordre"] == "anti_chronologique")

    rangs = [[valeur_colonne(l, c, fmt) for c in fmt["colonnes"]] for l in lignes]

    assainis = 0
    if fmt["guillemets"] == "jamais":
        propres = []
        for r in rangs:
            ligne = []
            for c in r:
                c, modifie = assainir(c, fmt["separateur"])
                assainis += modifie
                ligne.append(c)
            propres.append(ligne)
        rangs = propres
        quoting = csv.QUOTE_NONE
    else:
        quoting = csv.QUOTE_MINIMAL

    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=fmt["separateur"],
                          lineterminator=FINS_DE_LIGNE[fmt["fin_de_ligne"]],
                          quoting=quoting)

    # Chaque ligne de metadonnee est une liste de cellules, jamais du texte a
    # redecouper : une valeur contenant le separateur casserait le redecoupage.
    remplacements = {k: v for k, v in releve.items() if isinstance(v, (str, int))}
    for meta in fmt.get("lignes_avant_entete") or []:
        try:
            ecrivain.writerow([c.format(**remplacements) for c in meta])
        except KeyError as e:
            raise ErreurDeFormat(
                f"Une ligne de metadonnee du format reclame {{{e.args[0]}}}, "
                "qui n'existe pas dans le releve.\n"
                f"  Champs disponibles : {', '.join(sorted(remplacements)) or 'aucun'}.\n"
                "  Ajoutez-le au releve, ou ecrivez la valeur en clair dans le format."
            )
        except (ValueError, IndexError):
            raise ErreurDeFormat(
                f"Une ligne de metadonnee du format contient une accolade que le "
                f"script ne sait pas remplacer : {meta!r}.\n"
                "  Doublez les accolades litterales : {{ et }}."
            )

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
            "  remplacer au juge : le CSV n'a pas ete ecrit."
        )
    # Ecriture en un seul appel : une erreur en cours de route laisserait
    # sinon un fichier tronque a cote d'un rapport qui dit que tout va bien.
    try:
        sortie.write_bytes(octets)
    except FileNotFoundError:
        raise ErreurDeFormat(f"Le dossier de {sortie} n'existe pas.")
    except OSError as e:
        raise ErreurDeFormat(f"Impossible d'ecrire {sortie} : {e}")
    return len(rangs), assainis


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
    n, assainis = ecrire(releve, fmt, args.sortie, mesures["sens"])
    print(f"  {n} ligne(s) ecrite(s) -> {args.sortie}")
    print(f"  Format {fmt['nom']} : {fmt['encodage']}, {fmt['fin_de_ligne']}, "
          f"separateur « {fmt['separateur']} », ordre {fmt['ordre']}")
    if mesures["sens"] not in ORDRES_ADMIS:
        print("  Sens du releve indetermine (aucun solde par ligne) : l'ordre de")
        print("  sortie a ete etabli sur les dates seules.")
    if assainis:
        print(f"  {assainis} champ(s) assaini(s) : cette banque n'echappe pas les")
        print(f"  guillemets, le separateur « {fmt['separateur']} » a donc ete retire")
        print("  du texte des libelles concernes.")
    print()
    print("  Ce fichier est une TRANSCRIPTION d'un document scanne, pas un")
    print("  export d'origine de la banque. Dites-le en le transmettant.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
