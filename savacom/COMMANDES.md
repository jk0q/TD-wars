# Les commandes, dans l'ordre de la journée

## Le principe : rien ne s'installe chez Cédric

Son poste est un PC de comptable : pas de Python, et ce n'est pas le jour pour
en installer un. **Tu convertis sur ton portable.**

```
son poste  ──  fichier export  ──▶  ton portable  ──  CSV WinBiz  ──▶  son poste
              (clé USB / OneDrive)                   (clé USB / OneDrive)
```

Un aller-retour prend deux minutes. Prends une clé USB.

---

## Avant de partir — à faire maintenant, 5 minutes

### 1. Vérifier que Python est là

Ouvre un terminal (Windows : touche Windows puis tape `cmd` ; Mac : Terminal).

```bash
python --version
```

Si ça répond `Python 3.x` → c'est bon. Si ça répond une erreur, essaie
`python3 --version`. Si aucun des deux ne marche, installe Python depuis
python.org — **coche « Add Python to PATH »** pendant l'installation.

### 2. Récupérer les outils

```bash
git clone https://github.com/jk0q/TD-wars
cd TD-wars/savacom
```

Sans git : télécharge le ZIP depuis GitHub et dézippe-le.

### 3. Faire un essai à blanc

Mets `transactions(13).csv` dans ce dossier, puis :

```bash
python diagnostic.py "transactions(13).csv"
python ubs_vers_winbiz.py "transactions(13).csv" --limite 10
```

Si les deux affichent quelque chose, tu es prêt. **Ne pars pas sans avoir
fait cet essai.**

---

## Le plus simple : les deux lanceurs

Si la ligne de commande pose problème, tout le dossier fonctionne au
double-clic. Deux fichiers `.bat` sont fournis :

| Fichier | Ce qu'il fait |
|---|---|
| `1-DIAGNOSTIC.bat` | Glisse un CSV dessus, ou double-clique : il analyse tous les CSV du dossier |
| `2-CONVERTIR.bat` | Glisse l'export UBS dessus : il demande les comptes, puis convertit |

La fenêtre reste ouverte à la fin — le résultat se lit tranquillement.
Si Python manque, le lanceur le dit et explique quoi faire.

**Ouvrir un terminal dans le bon dossier**, si tu en as besoin quand même :
ouvre `cmd`, tape `cd ` suivi d'un espace, puis **glisse le dossier** depuis
l'explorateur dans la fenêtre noire, et Entrée. Cette méthode marche partout,
même quand `cmd` dans la barre d'adresse est bloqué.

---

## Sur place

### Étape 1 — Identifier ce qu'on te donne

Premier réflexe devant n'importe quel fichier, avant toute autre chose :

```bash
python diagnostic.py "le fichier de Cédric.csv"
```

Ça affiche en trois secondes : encodage, fin de ligne, séparateur, nombre de
colonnes, ce que contient chaque colonne, et les pièges (séparateur dans les
textes, sous-lignes, colonnes irrégulières).

Tu peux en passer plusieurs d'un coup :

```bash
python diagnostic.py *.csv
```

**Ce que tu regardes en priorité :**

| Ligne affichée | Ce que ça veut dire |
|---|---|
| `encodage : utf-8-sig` | WinBiz voudra du cp1252 — conversion nécessaire |
| `encodage : cp1252` | déjà au bon format |
| `fin de ligne : LF` | WinBiz veut du CRLF |
| `PIEGE : n champs contiennent le separateur` | c'est probablement la cause de l'échec |
| `A VERIFIER : n lignes sans valeur en 1re colonne` | des sous-lignes — risque de double comptage |

### Étape 2 — Le fichier de test à dix lignes

```bash
python ubs_vers_winbiz.py "transactions.csv" ^
    --compte-banque 1020 ^
    --compte-attente 9999 ^
    --journal BQ ^
    --limite 10
```

> Sur Windows, `^` en fin de ligne permet de continuer sur la suivante.
> Sur Mac et Linux, utilise `\` à la place.
> Ou écris tout sur une seule ligne, c'est identique.

Remplace `1020`, `9999` et `BQ` par les vraies valeurs que Cédric te donne.

Deux fichiers sortent :

- `transactions_winbiz.csv` → à importer dans WinBiz
- `transactions_rapport.txt` → **à lire avant d'importer**

### Étape 3 — Lire le rapport

```bash
type transactions_rapport.txt        # Windows
cat transactions_rapport.txt         # Mac / Linux
```

Trois lignes décident si tu importes ou non :

```
Chaine des soldes              : OK
Sous-montants et num. de piece : OK
```

et pas de section `ANOMALIES BLOQUANTES`.

**Si l'une de ces lignes n'est pas propre : n'importe pas.** Comprends d'abord.

### Étape 4 — Importer dans WinBiz

*Comptabilité → Écritures → Actions → Import/Export → Importation standard*

Regarde les dix écritures une par une avec Cédric.

### Étape 5 — Le fichier complet

Seulement une fois que les dix sont parfaites : la même commande **sans
`--limite`**.

```bash
python ubs_vers_winbiz.py "transactions.csv" --compte-banque 1020 --compte-attente 9999 --journal BQ
```

Vérifie dans le rapport que la **variation nette** correspond à
`solde final − solde initial` du relevé.

---

## Options utiles

| Option | À quoi ça sert |
|---|---|
| `--limite 10` | ne produire que 10 écritures — le fichier porte alors `_TEST` dans son nom |
| `--depuis 2026-01-01` | ne prendre qu'à partir d'une date |
| `--jusqua 2026-06-30` | ne prendre que jusqu'à une date |
| `--entete` | ajouter une ligne de titres, si WinBiz l'exige |
| `--longueur-libelle 40` | raccourcir les libellés si WinBiz les refuse |
| `--longueur-piece 10` | raccourcir les numéros de pièce |
| `-o sortie.csv` | choisir le nom du fichier produit |
| `--help` | revoir toutes les options |

Pour un seul mois, ce qui est exactement le cas de l'étape 5 du protocole :

```bash
python ubs_vers_winbiz.py "transactions.csv" --depuis 2026-07-01 --jusqua 2026-07-31 --compte-banque 1020 --compte-attente 9999 --journal BQ
```

---

## Si ça ne marche pas

**« en-tête introuvable — ce n'est pas un export UBS »**
Le fichier n'a pas la structure attendue. Lance `diagnostic.py` dessus et
envoie-moi le résultat : c'est probablement un autre format d'export, et il
faut adapter.

**Les accents sont en charabia dans WinBiz**
Le fichier produit est en cp1252, ce que WinBiz demande. Si ça casse quand
même, essaie `--entete` ou vérifie le paramétrage d'import de WinBiz.

**WinBiz refuse le fichier sans dire pourquoi**
Réduis à deux lignes : `--limite 2`. Puis retire des colonnes, ou ajoute
`--entete`. Procède par élimination sur un fichier minuscule, jamais sur le
gros.

**Les libellés sont coupés**
`--longueur-libelle 30`, et note la longueur maximale que WinBiz accepte.

**Python n'est pas trouvé**
Essaie `python3` au lieu de `python`, ou `py` sur Windows.

**Le script refuse une option**
Les options sont validées : une date doit être au format `AAAA-MM-JJ`, une
limite ne peut pas être négative, une longueur de pièce descend au minimum à 4.
Le message dit lequel et pourquoi.

**Un fichier de test n'écrase jamais le fichier de production.** Avec
`--limite`, la sortie s'appelle `<fichier>_TEST_winbiz.csv`.

---

## Ce que tu ramènes ce soir

Dans un dossier, avec les fichiers :

- La capture de l'écran d'importation WinBiz
- Le fichier d'import Raiffeisen qui fonctionne, s'il existe
- Les rapports de conversion produits
- Le message d'erreur exact, s'il y en a eu un
- La fiche de notes remplie

C'est ce qui permettra de finir le travail après.
