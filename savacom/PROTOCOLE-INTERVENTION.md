# Protocole de l'intervention sur place

À suivre dans l'ordre. Chaque étape produit une preuve — capture d'écran,
fichier ou chiffre noté. Une étape sans preuve n'est pas faite.

Périmètre : flux bancaire uniquement (ADR 0002).

---

## Avant de partir

- [ ] Convertisseur testé sur `transactions(13).csv`, rapport propre
- [ ] Table des mandats préremplie avec les trois IBAN connus
- [ ] Demande d'activation des CAMT lancée auprès de la BCN (ADR 0004)
- [ ] Ce protocole imprimé ou ouvert sur le téléphone

---

## Étape 1 — La capture qui débloque tout (15 min)

**Geste :** dans WinBiz, *Comptabilité → Écritures → Actions → Import/Export →
Importation standard*. Photographier l'écran qui liste les colonnes attendues.

**Ce qu'on cherche, dans l'ordre :**

1. L'ordre exact des colonnes et leur nombre
2. Un champ de référence au-delà de la colonne 7 — décide où loge la
   référence QR, et si la colonne Pièce reste libre pour le numéro de
   transaction (voir la tension Q8 / Q12)
3. Une ligne d'en-tête attendue ou non
4. La longueur maximale des champs Pièce et Libellé

**Preuve :** la capture. Sans elle, tout le reste de la journée est du réglage
à l'aveugle.

**Si l'écran ne dit rien :** importer un fichier de deux lignes fabriqué à la
main et regarder ce qui arrive dans WinBiz. Deux lignes, pas quatre cents.

---

## Étape 2 — Le fichier de référence (15 min)

**Geste :** demander à Cédric le dernier fichier d'import Raiffeisen qui a
fonctionné. Pas un export de banque : le fichier qu'il donne à WinBiz.

**Ce qu'on en fait :** l'ouvrir dans un éditeur de texte, jamais dans Excel.
Comparer colonne par colonne avec la sortie du convertisseur.

**Preuve :** une copie du fichier, et la liste écrite des écarts constatés.

**Si ce fichier n'existe pas** — c'est-à-dire si Cédric saisit à la main ou
passe par un autre chemin — le noter immédiatement : cela signifie que
personne n'a jamais réussi d'import CSV, et que « Raiffeisen OK » désignait
autre chose. Cela change le diagnostic de toute la mission.

---

## Étape 3 — Le premier import réel (45 min)

**Geste :** produire un fichier d'import limité à **dix écritures** du mandat
UBS, l'importer, regarder le résultat écriture par écriture.

```bash
python ubs_vers_winbiz.py transactions13.csv \
    --compte-banque <compte de Cédric> \
    --compte-attente <compte de Cédric> \
    --journal <code de Cédric>
```

**Ce qu'on vérifie :**

- Les accents s'affichent correctement dans WinBiz (encodage)
- Les libellés ne sont pas coupés au mauvais endroit (séparateur)
- Les montants ont le bon signe et le bon sens de compte
- Les dates tombent sur le bon exercice

**Preuve :** capture de WinBiz montrant les dix écritures.

**Règle absolue :** ne jamais passer à quatre cents écritures avant que dix
soient parfaites. Un import massif qui se révèle faux se corrige en heures.

---

## Étape 4 — Le chemin du justificatif (30 min, avec Thibault au téléphone)

**Geste :** sur **une seule** écriture, renseigner le chemin du justificatif et
tester le clic droit dans WinBiz.

**Ordre des essais :**

1. Chemin UNC : `\\NAS\...` — à privilégier, il survit à un changement de poste
2. Si WinBiz ne l'ouvre pas : lettre de lecteur `Z:\...`, en notant que le
   chemin devient dépendant de la session de Cédric

**Ce qu'on fixe définitivement ce jour-là :** la forme du chemin et
l'arborescence. Le chemin part en dur dans la base WinBiz : le modifier plus
tard casse tous les liens déjà importés.

**Preuve :** capture du justificatif ouvert depuis WinBiz par clic droit.

---

## Étape 5 — La comparaison CAMT contre CSV (1 h, pas plus)

Objectif : trancher entre les deux chemins par mesure, pas par discussion
(ADR 0007). **Un seul mandat, un seul mois.**

**Déroulé :**

1. Importer le mois M du mandat UBS par le convertisseur CSV. Noter :
   nombre d'écritures, solde reconstitué, minutes écoulées.
2. Annuler ou isoler cet import.
3. Importer le même mois M par la lecture CAMT native de WinBiz. Noter
   les trois mêmes chiffres.

**Grille de décision, dans cet ordre :**

| Critère | Comment le mesurer | Effet |
|---|---|---|
| Le solde est-il reconstitué ? | comparer au solde final du relevé | éliminatoire |
| Combien d'écritures restent à imputer ? | compter les lignes sur compte d'attente | critère principal |
| Combien de minutes pour un import propre ? | chronométrer, la 1re fois puis la suivante | départage |

**Preuve :** le tableau ci-dessus rempli avec des chiffres réels.

**Si le CAMT gagne :** le convertisseur ne disparaît pas — son contrôle de la
chaîne des soldes reste le seul moyen de vérifier ce que WinBiz a avalé.

**Si le temps manque :** cette étape passe avant l'étape 6. C'est elle qui
oriente les mois suivants.

---

## Étape 6 — Passage à l'échelle (45 min)

**Geste :** produire le fichier complet du mandat UBS, vérifier le rapport,
importer.

**Avant d'importer, le rapport doit afficher :**

- Chaîne des soldes : OK
- Sous-montants : OK
- Zéro anomalie bloquante

Si l'une de ces lignes n'est pas propre, ne pas importer. Comprendre d'abord.

**Preuve :** le rapport de conversion, et le solde WinBiz après import comparé
au solde final du relevé.

---

## Étape 7 — Transmission (30 min)

**Geste :** montrer à Cédric comment lancer le traitement lui-même, et lui
faire faire une fois devant vous.

**À laisser :** ce dépôt, la table des mandats renseignée, la capture de
l'écran d'import, et la liste écrite de ce qui reste ouvert.

---

## Ce qu'on ne fait pas ce jour-là

- Les factures fournisseurs (ADR 0002)
- Le rapprochement automatique des encaissements (ADR 0003)
- Toute imputation déduite d'un libellé (ADR 0008)
- Un import massif avant qu'un import de dix lignes soit parfait

---

## Notes à prendre pendant la journée

À reporter dans ce dépôt le soir même, tant que c'est frais :

- Comptes utilisés : banque, attente encaissements, attente décaissements
- Code journal
- Forme du chemin retenue et arborescence
- Ce que WinBiz affiche exactement quand un import échoue
- Nombre de mandats et volume mensuel réel
