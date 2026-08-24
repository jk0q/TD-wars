# Le traitement tourne sur le poste du comptable, derrière un raccourci unique

Le pipeline s'exécute sur la machine du comptable, lancé par un raccourci qu'il
double-clique et qui affiche le rapport à la fin. Aucune machine de
l'intégrateur n'intervient dans le traitement quotidien, et aucune ligne de
commande n'est exposée.

## Pourquoi

Le poste du comptable est le bon endroit : les données ne sortent pas de chez
le client, il n'y a pas de dépendance réseau, et le geste humain que l'ADR 0010
place déjà là s'y trouve naturellement.

Faire tourner le traitement chez l'intégrateur recréerait précisément la
dépendance à un prestataire dont la fiduciaire cherche à sortir en quittant
Multigest.

Mais exposer une ligne de commande à un comptable, c'est garantir qu'il ne s'en
servira pas. La différence entre un outil adopté et un outil abandonné tient
souvent à cette seule couche.
