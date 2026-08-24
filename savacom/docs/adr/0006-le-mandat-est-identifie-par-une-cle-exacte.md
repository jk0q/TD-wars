# Le mandat est identifié par une clé exacte, jamais déduit du contenu

Chaque pièce doit être rattachée à un mandat, qui détermine le dossier WinBiz,
le plan comptable et le dossier NAS. Le rattachement se fait par l'IBAN pour les
exports bancaires, et par le sous-dossier de dépôt choisi par le comptable pour
les factures fournisseurs. Le contenu du document n'est jamais utilisé pour
deviner le mandat.

## Pourquoi

L'IBAN est présent dans tous les formats d'export examinés : c'est une clé
gratuite et infaillible. Une facture fournisseur, elle, ne porte pas l'IBAN du
mandat mais celui du fournisseur — seul le geste de dépôt porte l'information.

Une pièce attribuée au mauvais mandat produit une écriture dans la comptabilité
d'une autre société. Le coût d'une erreur est sans commune mesure avec le
confort que la déduction automatique apporterait.

## Conséquences

- Un IBAN inconnu doit arrêter le traitement, jamais le poursuivre au jugé.
