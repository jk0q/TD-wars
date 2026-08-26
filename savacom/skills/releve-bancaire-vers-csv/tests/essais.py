#!/usr/bin/env python3
"""
Jeu d'essais du verificateur. Aucune dependance : `python3 tests/essais.py`.

Chaque cas passe par la vraie ligne de commande, pas par un import : ce qui
compte est ce qu'un utilisateur obtient — le code de sortie, le message, et
l'existence ou non du fichier de sortie.

Les cas nommes « REVUE » reproduisent un defaut trouve en revue de code. Ils
echouaient tous avant correction ; quatre d'entre eux produisaient un CSV faux
avec « Tous les controles passent » et un code de sortie 0.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
VERIFIER = RACINE / "scripts" / "verifier.py"

# Trois lignes, dont DEUX LE MEME JOUR : c'est ce qui revele les bugs d'ordre.
RELEVE = {
    "banque": "bcn",
    "iban": "CH17 0076 6000 1034 3068 1",
    "titulaire": "Voisin Serrurerie Sarl",
    "periode": {"debut": "2026-08-01", "fin": "2026-08-31"},
    "pages": {"lues": 3, "annoncees": 3},
    "totaux_imprimes": {"solde_initial": "1000.00", "solde_final": "700.00",
                        "total_debits": "300.00", "total_credits": "0.00"},
    "lignes": [
        {"date": "2026-08-03", "libelle": "A", "debit": "100.00", "solde": "900.00"},
        {"date": "2026-08-03", "libelle": "B", "debit": "100.00", "solde": "800.00"},
        {"date": "2026-08-05", "libelle": "C", "debit": "100.00", "solde": "700.00"},
    ],
}

FORMAT = {
    "banque": "test", "nom": "Banque de test", "statut": "mesure",
    "encodage": "cp1252", "fin_de_ligne": "CRLF", "separateur": ";",
    "guillemets": "jamais", "lignes_avant_entete": [["IBAN:", "{iban}"]],
    "entete": ["Date", "Texte", "Debit", "Credit", "Solde"],
    "ecrire_entete": True,
    "colonnes": ["date", "libelle", "debit", "credit", "solde"],
    "format_date": "%d.%m.%Y",
    "format_montant": {"decimales": 2, "separateur_decimal": ".",
                       "separateur_milliers": "aucun", "debit_negatif": False},
    "ordre": "anti_chronologique",
}


def modifier(base, **remplacements):
    """Copie profonde. Cle 'a__b__c' vise base['a']['b']['c']. Valeur None = suppression."""
    d = json.loads(json.dumps(base))
    for chemin, valeur in remplacements.items():
        *parents, cle = chemin.split("__")
        noeud = d
        for p in parents:
            noeud = noeud[int(p) if p.lstrip("-").isdigit() else p]
        cle = int(cle) if cle.lstrip("-").isdigit() else cle
        if valeur is None:
            del noeud[cle]
        else:
            noeud[cle] = valeur
    return d


class Bac:
    def __init__(self, dossier):
        self.d = Path(dossier)

    def _json(self, nom, contenu):
        p = self.d / nom
        p.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
        return p

    def lancer(self, *args):
        r = subprocess.run([sys.executable, str(VERIFIER), *map(str, args)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def controler(self, releve=None):
        return self.lancer("controler", self._json("r.json", releve or RELEVE))

    def ecrire(self, releve=None, fmt=None, sortie="out.csv", chemin_format=None):
        s = self.d / sortie
        f = chemin_format or self._json("f.json", fmt or FORMAT)
        code, txt = self.lancer("ecrire", self._json("r.json", releve or RELEVE),
                                "--format", f, "-o", s)
        return code, txt, (s.read_bytes() if s.exists() else None)


ESSAIS = []


def essai(f):
    ESSAIS.append(f)
    return f


def colonne_solde(octets, fmt=FORMAT):
    """Renvoie la colonne des soldes du CSV produit, dans l'ordre du fichier."""
    texte = octets.decode(fmt["encodage"])
    lignes = [l for l in texte.split("\r\n" if fmt["fin_de_ligne"] == "CRLF" else "\n") if l]
    corps = lignes[len(fmt["lignes_avant_entete"]) + (1 if fmt["ecrire_entete"] else 0):]
    return [l.split(fmt["separateur"])[-1] for l in corps]


# =========================================================================
# Contrôles — ce qui doit passer
# =========================================================================

@essai
def controle_releve_juste(b):
    code, txt = b.controler()
    assert code == 0, txt
    assert "Tous les controles passent" in txt
    assert "chronologique" in txt and "anti_chronologique" not in txt


@essai
def controle_sens_anti_chronologique(b):
    r = modifier(RELEVE)
    r["lignes"] = list(reversed(r["lignes"]))
    code, txt = b.controler(r)
    assert code == 0, txt
    assert "anti_chronologique" in txt


@essai
def REVUE_soldes_imprimes_par_intermittence(b):
    """Un relevé n'imprime souvent un solde que sur certaines lignes.

    Avant correction : la chaîne ne cumulait pas les mouvements des lignes
    intermédiaires et fabriquait une rupture BLOQUANTE sur un relevé juste,
    en envoyant relire une ligne qui n'avait rien.
    """
    code, txt = b.controler(modifier(RELEVE, lignes__1__solde=None))
    assert code == 0, txt
    assert "ANOMALIES" not in txt, txt


# =========================================================================
# Contrôles — ce qui doit bloquer
# =========================================================================

@essai
def bloque_chiffre_mal_lu(b):
    r = modifier(RELEVE, lignes__1__debit="100.02", lignes__1__solde="799.98",
                 lignes__2__solde="699.98")
    code, txt = b.controler(r)
    assert code == 1 and "ecart 0.02" in txt, txt


@essai
def bloque_ligne_sautee(b):
    r = modifier(RELEVE)
    del r["lignes"][1]
    code, txt = b.controler(r)
    assert code == 1 and "chaine des soldes" in txt, txt


@essai
def bloque_page_manquante(b):
    code, txt = b.controler(modifier(RELEVE, pages__lues=2))
    assert code == 1 and "releve incomplet" in txt, txt


@essai
def bloque_lecture_douteuse(b):
    r = modifier(RELEVE, lignes__1__confiance="douteuse", lignes__1__note="pliure")
    code, txt = b.controler(r)
    assert code == 1 and "douteuse : pliure" in txt, txt


@essai
def REVUE_bloque_ligne_sans_date(b):
    """Avant correction : passait tous les contrôles, sortait en 0, et se
    retrouvait dans le CSV avec une cellule date vide."""
    code, txt = b.controler(modifier(RELEVE, lignes__1__date=None))
    assert code == 1 and "pas de date" in txt, txt


@essai
def bloque_debit_et_credit(b):
    code, txt = b.controler(modifier(RELEVE, lignes__0__credit="50.00"))
    assert code == 1 and "debit ET credit" in txt, txt


@essai
def bloque_ni_debit_ni_credit(b):
    code, txt = b.controler(modifier(RELEVE, lignes__0__debit=None))
    assert code == 1 and "ni debit ni credit" in txt, txt


@essai
def REVUE_bloque_montant_non_fini(b):
    """« NaN » est un Decimal valide : il explosait à la première comparaison."""
    code, txt = b.controler(modifier(RELEVE, lignes__0__debit="NaN"))
    assert code == 1 and "Traceback" not in txt, txt


@essai
def REVUE_banque_nulle_ne_plante_pas(b):
    """.get(cle, defaut) ne couvre pas une clé présente à null."""
    code, txt = b.controler(modifier(RELEVE, banque=None))
    assert "Traceback" not in txt, txt
    assert "CONTROLE DU RELEVE" in txt


@essai
def json_invalide_message_clair(b):
    (b.d / "casse.json").write_text("{pas du json", encoding="utf-8")
    code, txt = b.lancer("controler", b.d / "casse.json")
    assert code == 1 and "n'est pas du JSON valide" in txt and "Traceback" not in txt


# =========================================================================
# Fichier de format — validation avant le premier octet
# =========================================================================

def _refus(b, attendu, **remplacements):
    code, txt, octets = b.ecrire(fmt=modifier(FORMAT, **remplacements))
    assert code == 1, f"attendu un refus, recu 0\n{txt}"
    assert "Traceback" not in txt, txt
    assert attendu in txt, f"message attendu {attendu!r}\n{txt}"
    assert octets is None, "un fichier a ete ecrit malgre le refus"


@essai
def refuse_format_non_mesure(b):
    _refus(b, "pas encore ete mesure", statut="indicatif")


@essai
def REVUE_refuse_encodage_recopie_du_diagnostic(b):
    """diagnostic.py affiche « Windows-1252 (ANSI) ». Recopié tel quel, ça
    levait un LookupError brut au moment de l'encodage."""
    _refus(b, "n'est pas un encodage connu", encodage="Windows-1252 (ANSI)")


@essai
def REVUE_refuse_fin_de_ligne_recopiee_du_diagnostic(b):
    """« CRLF (Windows) » recopié tel quel : chaque ligne du CSV se terminait
    par le texte « (Windows) », sans un mot, code 0."""
    _refus(b, "attendu « CRLF » ou « LF »", fin_de_ligne="CRLF (Windows)")


@essai
def REVUE_refuse_ordre_inconnu(b):
    """postfinance.json porte « ordre »: « inconnu ». Avant correction, toute
    valeur non vide passait et le fichier sortait en chronologique."""
    _refus(b, "attendu « chronologique »", ordre="inconnu")


@essai
def REVUE_refuse_ordre_mal_orthographie(b):
    _refus(b, "attendu « chronologique »", ordre="ANTI_CHRONOLOGIQUE")


@essai
def REVUE_refuse_debit_negatif_non_booleen(b):
    """La phrase descriptive de _MODELE.json laissée en place activait
    silencieusement l'inversion de signe de tous les débits."""
    _refus(b, "doit valoir true ou false",
           format_montant__debit_negatif="true si les debits portent un signe moins")


@essai
def REVUE_refuse_format_date_gabarit(b):
    """Le texte d'exemple de _MODELE.json remplissait chaque cellule date."""
    # La chaine exacte de formats/_MODELE.json, pas une approximation.
    _refus(b, "n'est pas un format de date utilisable",
           format_date="%d.%m.%Y | %Y-%m-%d | %d/%m/%y — tel qu'il apparait dans l'export")


@essai
def REVUE_refuse_format_sans_nom(b):
    """« nom » n'était pas dans les champs requis et n'était lu qu'APRES
    l'écriture : le CSV restait sur le disque à côté d'un code 1."""
    _refus(b, "« nom » manquant", nom=None)


@essai
def refuse_entete_et_colonnes_desaccordees(b):
    _refus(b, "Les deux listes doivent correspondre",
           colonnes=["date", "libelle", "debit"])


@essai
def refuse_colonne_inconnue(b):
    _refus(b, "inconnu", colonnes=["date", "libelle", "debit", "credit", "reference"])


@essai
def refuse_separateur_multi_caracteres(b):
    _refus(b, "un seul caractere", separateur=";;")


@essai
def refuse_metadonnee_en_chaine(b):
    _refus(b, "liste de cellules", lignes_avant_entete=["IBAN:;{iban}"])


@essai
def REVUE_refuse_placeholder_inconnu(b):
    """postfinance.json réclame {devise}, absent du relevé : KeyError brut."""
    _refus(b, "qui n'existe pas dans le releve",
           lignes_avant_entete=[["Devise:", "{devise}"]])


@essai
def REVUE_format_introuvable_message_clair(b):
    code, txt, octets = b.ecrire(chemin_format=b.d / "inexistant.json")
    assert code == 1 and "introuvable" in txt and "Traceback" not in txt, txt


@essai
def REVUE_dossier_de_sortie_absent(b):
    code, txt, _ = b.ecrire(sortie="pas/la/out.csv")
    assert code == 1 and "Traceback" not in txt, txt
    assert "n'existe pas" in txt, txt


# =========================================================================
# Écriture
# =========================================================================

@essai
def REVUE_ordre_respecte_les_lignes_du_meme_jour(b):
    """Deux écritures du même jour. Le tri de Python est stable : trier par
    date ne les réordonnait JAMAIS, et la colonne des soldes sortait dans le
    désordre — code 0, aucune anomalie."""
    code, txt, octets = b.ecrire()
    assert code == 0, txt
    assert colonne_solde(octets) == ["700.00", "800.00", "900.00"], colonne_solde(octets)


@essai
def ordre_chronologique_demande(b):
    code, txt, octets = b.ecrire(fmt=modifier(FORMAT, ordre="chronologique"))
    assert code == 0, txt
    f = modifier(FORMAT, ordre="chronologique")
    assert colonne_solde(octets, f) == ["900.00", "800.00", "700.00"]


@essai
def octets_conformes_au_format(b):
    code, txt, octets = b.ecrire()
    assert code == 0, txt
    assert octets.count(b"\r\n") == 5 and octets.count(b"\n") == 5
    assert octets.decode("cp1252").startswith("IBAN:;CH17")
    assert all(l.count(b";") in (1, 4) for l in octets.split(b"\r\n") if l)


@essai
def REVUE_separateur_milliers_espace(b):
    """_MODELE.json sanctionne « espace ». Il était écrit littéralement :
    1234567.89 devenait « 1espace234espace567.89 »."""
    r = modifier(RELEVE,
                 totaux_imprimes__solde_initial="1234867.89",
                 totaux_imprimes__solde_final="1234567.89",
                 lignes__0__solde="1234767.89", lignes__1__solde="1234667.89",
                 lignes__2__solde="1234567.89")
    f = modifier(FORMAT, format_montant__separateur_milliers="espace")
    code, txt, octets = b.ecrire(releve=r, fmt=f)
    assert code == 0, txt
    assert "1 234 567.89" in octets.decode("cp1252"), octets.decode("cp1252")


@essai
def separateur_milliers_apostrophe(b):
    r = modifier(RELEVE,
                 totaux_imprimes__solde_initial="1234867.89",
                 totaux_imprimes__solde_final="1234567.89",
                 lignes__0__solde="1234767.89", lignes__1__solde="1234667.89",
                 lignes__2__solde="1234567.89")
    f = modifier(FORMAT, format_montant__separateur_milliers="'")
    code, txt, octets = b.ecrire(releve=r, fmt=f)
    assert code == 0 and "1'234'567.89" in octets.decode("cp1252"), txt


@essai
def REVUE_guillemets_jamais_survit_a_un_guillemet(b):
    """QUOTE_NONE sans escapechar levait csv.Error — trace brute — dès qu'un
    libellé contenait un guillemet ou un retour à la ligne."""
    r = modifier(RELEVE, lignes__0__libelle='Virement "urgent";\nfrais de tiers')
    code, txt, octets = b.ecrire(releve=r)
    assert code == 0, txt
    assert "Traceback" not in txt
    assert "assaini" in txt, txt
    ligne = [l for l in octets.decode("cp1252").split("\r\n") if "Virement" in l][0]
    assert ligne.count(";") == 4, ligne


@essai
def debit_negatif_inverse_le_signe(b):
    f = modifier(FORMAT, format_montant__debit_negatif=True)
    code, txt, octets = b.ecrire(fmt=f)
    assert code == 0 and ";-100.00;" in octets.decode("cp1252"), txt


@essai
def colonne_signee_unique(b):
    f = modifier(FORMAT, entete=["Date", "Texte", "Montant"],
                 colonnes=["date", "libelle", "montant"])
    code, txt, octets = b.ecrire(fmt=f)
    assert code == 0, txt
    assert ";-100.00" in octets.decode("cp1252"), octets.decode("cp1252")


@essai
def rien_ecrit_si_un_controle_echoue(b):
    code, txt, octets = b.ecrire(releve=modifier(RELEVE, pages__lues=1))
    assert code == 1 and octets is None, "un CSV a ete ecrit malgre une anomalie"


@essai
def caractere_hors_encodage_refuse_sans_ecrire(b):
    code, txt, octets = b.ecrire(releve=modifier(RELEVE, lignes__0__libelle="Facture ☎"))
    assert code == 1 and octets is None and "Traceback" not in txt, txt
    assert "n'existe pas en cp1252" in txt, txt


# =========================================================================
# Les deux copies de diagnostic.py
# =========================================================================

@essai
def REVUE_les_deux_diagnostic_ne_derivent_pas(b):
    """diagnostic.py est volontairement recopie dans la skill, pour qu'elle
    fonctionne seule une fois televersee. Deux copies sans mecanisme de
    synchronisation derivent : cet essai compare le CODE des deux, en ignorant
    les docstrings — qui, elles, ont le droit de differer et different deja.

    Ne s'applique que dans le depot ; ignore quand la skill voyage seule.
    """
    import ast

    jumeau = RACINE.parent.parent / "diagnostic.py"
    if not jumeau.exists():
        return  # skill packagee seule : rien a comparer

    def sans_docstrings(source: str) -> str:
        arbre = ast.parse(source)
        porteurs = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, porteurs) and noeud.body:
                tete = noeud.body[0]
                if (isinstance(tete, ast.Expr) and isinstance(tete.value, ast.Constant)
                        and isinstance(tete.value.value, str)):
                    noeud.body = noeud.body[1:]
        return ast.dump(arbre)

    ici = RACINE / "scripts" / "diagnostic.py"
    assert sans_docstrings(ici.read_text(encoding="utf-8")) == \
           sans_docstrings(jumeau.read_text(encoding="utf-8")), (
        f"le code de {ici} et celui de {jumeau} ont derive.\n"
        "      Reportez la correction dans les deux, ou supprimez l'une des copies.")


# =========================================================================

def main() -> int:
    largeur = max(len(f.__name__) for f in ESSAIS)
    echecs = []
    for f in ESSAIS:
        with tempfile.TemporaryDirectory() as d:
            try:
                f(Bac(d))
                etat = "ok"
            except AssertionError as e:
                etat, _ = "ECHEC", echecs.append((f.__name__, str(e)))
            except Exception as e:
                etat, _ = "ERREUR", echecs.append((f.__name__, f"{type(e).__name__} : {e}"))
        print(f"  {f.__name__:<{largeur}}  {etat}")

    print()
    if echecs:
        print(f"  {len(echecs)} echec(s) sur {len(ESSAIS)} :")
        for nom, detail in echecs:
            print(f"\n  --- {nom}")
            for l in detail.splitlines()[:12]:
                print(f"      {l}")
        return 1
    print(f"  {len(ESSAIS)} essais, tous passent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
