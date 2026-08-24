# La conversion est du code déterministe ; le modèle ne sert qu'au jugement

Le brief de mission décrit une « automatisation des flux comptables via Claude »,
ce qui laisse entendre que le modèle lit les fichiers et produit les écritures.
Nous plaçons la frontière ailleurs : tout ce qui est mécanique — lire un export
bancaire, fusionner les sous-lignes, contrôler les invariantes, écrire le fichier
d'import — est du code déterministe ; le modèle n'intervient que là où un
jugement est requis et où aucune règle ne s'écrit : lire un relevé scanné,
reconnaître un fournisseur, ventiler une TVA multi-taux.

## Pourquoi

Un modèle qui recopie 770 montants finira par en abîmer un, sans que rien ne le
signale et sans qu'on puisse dire lequel. Un script ne se trompe jamais deux fois
de la même façon, se teste contre une invariante, et se relit par un tiers.
La comptabilité ne tolère pas l'erreur silencieuse : c'est le critère qui tranche.

## Conséquences

- Les invariantes du domaine (chaîne des soldes, cohérence des sous-montants,
  reconstitution de la variation de solde) deviennent le juge de la conversion,
  et non l'absence de plantage.
- Le convertisseur refuse de produire un fichier lorsqu'une invariante est
  violée, plutôt que d'en produire un faux.
- Aucune imputation n'est devinée : la contrepartie part sur un compte d'attente
  et ressort dans le rapport d'exécution.
- La documentation attendue au point 12 de la mission est le code lui-même,
  et non un recueil de prompts à maintenir.
