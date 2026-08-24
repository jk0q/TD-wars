# Deux journaux : un rapport par exécution, un journal cumulatif par mandat

Chaque exécution produit un rapport lisible immédiatement. En parallèle, un
journal cumulatif par mandat s'enrichit à chaque passage et n'est jamais purgé.

## Pourquoi

Le rapport sert à décider maintenant : importer ou comprendre d'abord. Le
journal cumulatif sert le jour où une écriture est contestée plusieurs mois
après — et en fiduciaire, ce jour arrive.

Le journal est aussi ce qui rend le registre des doublons (ADR 0011) auditable :
sans lui, il est impossible d'expliquer pourquoi une transaction a été écartée,
et un écartement inexpliqué est indiscernable d'une perte de donnée.

## Conséquences

- Une information absente du journal est définitivement perdue : le contenu du
  journal se décide avant la mise en production, pas après.
