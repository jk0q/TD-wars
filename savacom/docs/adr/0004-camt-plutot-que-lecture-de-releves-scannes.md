# La source bancaire est le fichier CAMT de la banque, jamais un relevé scanné

La mission demande de traiter « PDF natifs, scans et images ». Pour le flux
bancaire, nous refusons cette entrée : la source est le fichier CAMT.053 ou
CAMT.054 fourni par la banque. Le relevé BCN reçu en papier scanné est
abandonné au profit des CAMT disponibles via BCN-Direct.

## Pourquoi

Reconstituer par reconnaissance optique des montants qui existent déjà sous
forme structurée chez la banque est un travail contre soi-même. Le CAMT porte
en outre les références de paiement structurées, que le scan et les exports
appauvris ont perdues. Une demande d'activation auprès de la banque coûte un
appel téléphonique ; un lecteur de scan fiable coûte des jours et ne le sera
jamais totalement.

## Conséquences

- Dépendance externe à délai : l'activation des CAMT chez la banque doit être
  lancée avant l'intervention, faute de quoi le mandat concerné reste bloqué.
- La reconnaissance optique reste nécessaire pour les factures fournisseurs,
  hors du périmètre retenu (voir ADR 0002).
- Un relevé scanné doit être rendu en respectant l'attribut `/Rotate` de la
  page, et non extrait comme image embarquée : le bitmap est stocké pivoté.
