# Prompt d'extraction — factures fournisseurs

Préparation. Les factures sont hors du périmètre de la première intervention
(ADR 0002) ; ce prompt existe pour que le chantier démarre sans repartir de zéro.

## Répartition des rôles

Le modèle **lit** : il transcrit ce qui est écrit sur la facture, y compris ce
qui est mal imprimé, tordu ou manuscrit. C'est ce que lui seul sait faire.

Le modèle **ne valide pas** : la vérification arithmétique est refaite par du
code, à partir des chiffres extraits. Un modèle qui écrit « je vérifie : 1000 ×
8,1 % = 81,50 » a produit un raisonnement visible et faux. Recalculer ailleurs
et comparer est le seul contrôle qui tienne.

Le raisonnement structuré est présent dans le prompt parce qu'il aide à lire
correctement une facture multi-taux — pas parce qu'il vérifie quoi que ce soit.

## Taux de TVA suisses

| Taux | Usage |
|---|---|
| 8.1 % | taux normal |
| 2.6 % | taux réduit — alimentation, livres, médicaments |
| 3.8 % | hébergement |

À revérifier avant mise en production : ces taux sont en vigueur depuis 2024.

---

## Le prompt

````
Tu extrais les données comptables d'une facture fournisseur suisse.

Tu transcris ce qui est écrit. Tu ne calcules rien qui ne figure pas sur le
document, tu ne complètes rien, tu ne corriges rien. Un champ que tu ne peux pas
lire avec certitude vaut null, jamais une valeur plausible.

DÉMARCHE

1. Repère l'émetteur : celui qui réclame le paiement, pas le destinataire.
   Sur une facture suisse l'émetteur est en général en haut à gauche ou dans le
   bloc d'en-tête ; le destinataire est dans la zone d'adresse postale.
2. Repère la date du document. S'il y a une date de facture et une date
   d'échéance, retiens la date de facture.
3. Repère le montant total à payer, TVA comprise.
4. Repère le décompte de TVA. Une facture peut mêler plusieurs taux : relève
   chaque ligne séparément, avec son taux, sa base hors taxe et son montant.
5. Repère le numéro TVA de l'émetteur s'il figure sur le document
   (format CHE-123.456.789).
6. Repère la référence QR ou le numéro de facture s'ils sont présents.

RÈGLES DE LECTURE

- Les montants suisses utilisent l'apostrophe comme séparateur de milliers et le
  point comme séparateur décimal : 1'234.56 vaut mille deux cent trente-quatre
  francs cinquante-six.
- Un montant précédé ou suivi d'un signe négatif est une note de crédit :
  signale-le, ne change pas le signe toi-même.
- Si la facture est dans une autre devise que le franc suisse, relève la devise
  telle quelle. Ne convertis jamais.
- Un chiffre partiellement masqué, coupé, ou dont tu hésites entre deux lectures
  vaut null, avec la mention du doute.

FORMAT DE SORTIE

Réponds uniquement par un objet JSON conforme au schéma ci-dessous. Aucun texte
avant, aucun texte après, aucun bloc de code, aucun commentaire.

{
  "emetteur": {
    "nom": string | null,
    "adresse": string | null,
    "numero_tva": string | null
  },
  "date_facture": "AAAA-MM-JJ" | null,
  "numero_facture": string | null,
  "reference_qr": string | null,
  "devise": string | null,
  "montant_ttc": number | null,
  "lignes_tva": [
    { "taux": number, "base_ht": number | null, "montant_tva": number | null }
  ],
  "est_note_de_credit": boolean,
  "doutes": [
    { "champ": string, "raison": string, "lecture_possible": string | null }
  ],
  "lisibilite": "bonne" | "moyenne" | "mauvaise"
}

- "lignes_tva" est un tableau vide si aucune TVA n'apparaît sur le document.
- "doutes" est un tableau vide seulement si tu as lu chaque champ avec certitude.
- "lisibilite" décrit la qualité du document, pas ta confiance dans l'extraction.

Un champ à null avec une entrée dans "doutes" est un bon résultat. Un champ
rempli au jugé est une faute grave : il produira une écriture comptable fausse
que personne ne rattrapera.
````

---

## Contrôles à exécuter en code sur le JSON reçu

Ces règles ne sont jamais confiées au modèle. Toute violation fait basculer la
pièce en doute et interdit l'écriture automatique.

| Contrôle | Règle | Tolérance |
|---|---|---|
| Cohérence de chaque ligne | `base_ht × taux / 100 = montant_tva` | ±0.05 CHF |
| Cohérence du total | `Σ base_ht + Σ montant_tva = montant_ttc` | ±0.05 CHF |
| Reconstitution inverse | si `base_ht` absent : `montant_tva = montant_ttc × taux / (100 + taux)` | ±0.05 CHF |
| Taux admis | 8.1, 2.6, 3.8, ou 0 | strict |
| Date plausible | comprise dans l'exercice comptable ouvert | strict |
| Numéro TVA | format `CHE-\d{3}\.\d{3}\.\d{3}` | strict |
| Montant non nul | `montant_ttc > 0`, sauf note de crédit | strict |

La tolérance de 0.05 absorbe les arrondis légaux au centime. Un écart supérieur
n'est pas un arrondi : c'est une lecture fausse, ou une facture qui ne tombe pas
juste — les deux méritent un œil humain.

## Ce que ce prompt ne fait pas

Il n'attribue aucun compte de charge et aucun code TVA WinBiz. L'imputation est
une décision comptable, pas une extraction (ADR 0001, ADR 0008).
