# Le dépôt est la documentation ; aucun document de synthèse séparé

Le livrable de maintenance est ce dépôt : le code, le glossaire, les décisions
d'architecture et le protocole d'intervention. Aucun document de synthèse
parallèle n'est produit.

## Pourquoi

Le brief demandait de « documenter les prompts, règles et configurations
finales ». L'ADR 0001 ayant déplacé l'essentiel dans du code déterministe, il
n'y a pas de recueil de prompts à maintenir : la documentation utile est le code
et les raisons de ses choix.

Un document de synthèse séparé se périmerait dès la première modification du
code, et personne ne le mettrait à jour. C'est exactement ainsi que la
documentation de la solution précédente est devenue inutilisable.

## Conséquences

- Le dépôt doit ouvrir sur une page d'entrée qui dise par où commencer et ce
  qui reste ouvert, faute de quoi il est illisible pour un nouveau venu.
- Toute décision prise sur place doit être reportée dans le dépôt le soir même.
