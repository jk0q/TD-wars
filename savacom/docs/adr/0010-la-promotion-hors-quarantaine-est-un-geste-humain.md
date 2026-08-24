# La sortie de quarantaine est déclenchée par le comptable, jamais automatiquement

Une pièce quitte la quarantaine pour son dossier d'archive sur commande
explicite du comptable, après qu'il a constaté que l'import est passé. Le
pipeline ne relit pas la base WinBiz pour s'en assurer, et rien ne part à
l'archive par expiration de délai.

## Pourquoi

WinBiz ne renvoie aucun signal exploitable après un import : il n'existe pas de
confirmation machine à attendre. Relire la base rouvrirait la dépendance que
l'ADR 0003 vient d'écarter. Archiver après un délai reviendrait à classer des
pièces dont personne n'a confirmé qu'elles sont comptabilisées — précisément la
panne silencieuse que le reste du système cherche à éviter.

## Conséquences

- L'objectif « zero-touch » du brief est explicitement abandonné au profit d'un
  point de contrôle unique, situé là où le comptable regarde déjà son écran.
  C'est le seul geste manuel du flux, et il est délibéré.
