# Prompt d'extraction — factures fournisseurs

Préparation. Les factures sont hors du périmètre de la première intervention
(ADR 0002) ; ce prompt existe pour que le chantier démarre sans repartir de zéro.

## Répartition des rôles

Trois tâches différentes se cachent derrière le mot « TVA », et chacune appelle
un outil différent.

**Lire les montants** — transcription. Seul le modèle sait déchiffrer un scan
tordu ou une mention manuscrite.

**Vérifier que les montants tombent juste** — code. Un modèle qui écrit
« je vérifie : 1000 × 8,1 % = 81,50 » a produit un raisonnement visible et faux.
Un calcul ne se vérifie pas en le racontant : il se vérifie en le refaisant
ailleurs et en comparant.

**Attribuer le bon taux à la bonne ligne** — raisonnement structuré. C'est un
jugement, pas une lecture, et un jugement gagne à être déroulé.

Sur une facture suisse conforme, cette troisième tâche ne se pose pas : la loi
impose que le taux figure sur le document, on le lit. Elle se pose sur tout le
reste — tickets de caisse, notes d'hôtel, fournisseurs étrangers — et c'est
précisément là que le raisonnement gagne sa place.

La limite : le raisonnement sert à **attribuer** un taux parmi ceux que le
document permet, jamais à en **inventer** un absent. Chaque ligne de TVA porte
donc un champ `source` valant `"lu"` ou `"deduit"`. Une ligne `"lu"` est une
transcription ; une ligne `"deduit"` est un jugement, et elle passe sous les yeux
du comptable. C'est ce qui rend le raisonnement auditable au lieu d'invisible.

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

ATTRIBUTION DES TAUX

Si le document indique explicitement ses taux, transcris-les et marque chaque
ligne "source": "lu". C'est le cas normal : la loi suisse impose que le taux
figure sur une facture conforme.

Si le document n'indique pas de taux, ou en indique un pour plusieurs natures de
prestation, déroule ton raisonnement avant de répondre, dans cet ordre :

  a. Quelle est la nature de chaque prestation facturée ?
  b. Le fournisseur est-il assujetti en Suisse ? Un fournisseur étranger sans
     numéro TVA suisse ne facture pas de TVA suisse — signale-le et laisse
     "lignes_tva" vide.
  c. Quel taux correspond à chaque nature ?
       8.1 %  taux normal — le cas par défaut
       2.6 %  taux réduit — alimentation à l'emporter, boissons sans alcool,
              livres, journaux, médicaments
       3.8 %  hébergement — la nuitée seule, pas les prestations annexes
  d. Reste-t-il une ambiguïté que le document ne tranche pas ?

Cas fréquents qui demandent ce raisonnement :
  - Restauration : consommé sur place 8.1 %, emporté 2.6 %. Cherche l'indice
    dans le document (mention "take away", type d'établissement, service).
  - Hôtellerie : nuitée 3.8 %, petit-déjeuner et parking 8.1 %. Une note groupée
    mélange donc plusieurs taux.
  - Fournisseur étranger : pas de TVA suisse récupérable.
  - Fournisseur sans numéro TVA : aucune TVA récupérable, même si un montant
    apparaît.

Toute ligne obtenue par ce raisonnement porte "source": "deduit", et une entrée
correspondante dans "doutes" expliquant sur quoi tu t'es appuyé. Si le
raisonnement ne tranche pas, ne choisis pas : laisse la ligne hors du tableau et
décris l'ambiguïté dans "doutes".

Tu n'inventes jamais un taux qui ne correspond à aucune des trois valeurs
ci-dessus.

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
    {
      "taux": number,
      "base_ht": number | null,
      "montant_tva": number | null,
      "source": "lu" | "deduit",
      "justification": string | null
    }
  ],
  "fournisseur_assujetti_suisse": boolean | null,
  "est_note_de_credit": boolean,
  "doutes": [
    { "champ": string, "raison": string, "lecture_possible": string | null }
  ],
  "lisibilite": "bonne" | "moyenne" | "mauvaise"
}

- "lignes_tva" est un tableau vide si aucune TVA n'apparaît sur le document, ou
  si le fournisseur n'est pas assujetti en Suisse.
- "source" vaut "lu" quand le taux est imprimé sur le document, "deduit" quand tu
  l'as attribué par raisonnement. "justification" est obligatoire pour "deduit"
  et vaut null pour "lu".
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
| Ligne déduite | toute ligne `source: "deduit"` force la relecture humaine | strict |
| Fournisseur non assujetti | `lignes_tva` doit être vide | strict |

La tolérance de 0.05 absorbe les arrondis légaux au centime. Un écart supérieur
n'est pas un arrondi : c'est une lecture fausse, ou une facture qui ne tombe pas
juste — les deux méritent un œil humain.

Le champ `source` sépare deux populations qu'il ne faut jamais confondre dans un
rapport : ce que le modèle a lu, et ce qu'il a jugé. Le premier se contrôle par
l'arithmétique ; le second ne se contrôle que par un humain.

## Ce que ce prompt ne fait pas

Il n'attribue aucun compte de charge et aucun code TVA WinBiz. L'imputation est
une décision comptable, pas une extraction (ADR 0001, ADR 0008).
