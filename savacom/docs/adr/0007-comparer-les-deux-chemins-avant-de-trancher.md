# Le chemin bancaire — CAMT natif ou conversion CSV — est tranché par comparaison, pas par principe

WinBiz lit nativement les CAMT.053 et 054, avec un moteur de règles qui mémorise
les attributions et les rejoue. Notre convertisseur produit un fichier d'import
à partir de l'export e-banking. Les deux chemins mènent aux mêmes écritures.
Nous refusons de choisir à l'avance : un même mois d'un même mandat sera importé
par les deux chemins et le résultat départagera.

## Pourquoi

Le CAMT natif est la cible probable — il supprime toute conversion et donc toute
occasion de se tromper. Mais le moteur de règles WinBiz produit des attributions
que personne n'audite, là où le convertisseur produit un rapport qui dit ce
qu'il a fait et ce dont il doute. C'est un arbitrage entre simplicité et
traçabilité, et aucun raisonnement en chambre ne le tranche.

## Conséquences

- Si le CAMT natif l'emporte, le convertisseur n'est pas perdu : son contrôle de
  la chaîne des soldes reste le seul moyen de vérifier ce que WinBiz a avalé.
- Si le comptable impose la conversion CSV par habitude, elle est maintenue pour
  UBS et Raiffeisen, la BCN passant au CAMT faute de source structurée
  alternative.
