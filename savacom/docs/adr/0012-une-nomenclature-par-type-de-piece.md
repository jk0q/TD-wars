# Chaque type de pièce a sa nomenclature, et la date est en tête au format ISO

Une facture est nommée `AAAA-MM-JJ_Fournisseur_Montant.pdf`, un relevé bancaire
`AAAA-MM_Banque_Mandat.pdf`. Deux pièces produisant le même nom reçoivent un
suffixe numérique, tracé en avertissement.

## Pourquoi

La nomenclature `Date_Fournisseur_Montant` proposée par le brief ne convient
qu'aux factures : un relevé bancaire n'a pas de fournisseur et son montant n'a
pas de sens. Forcer un gabarit unique produirait des noms à champs vides.

La date en tête au format ISO trie correctement dans l'explorateur Windows, ce
que `JJ.MM.AAAA` ne fait pas. Détail minuscule, utilisé tous les jours pendant
des années.

Le suffixe est préféré à l'arrêt du traitement : une collision de nom est un
inconvénient, pas une menace pour l'exactitude comptable.
