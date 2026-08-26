# La transcription d'un scan ne s'emploie qu'à défaut d'accès au fichier de la banque

L'ADR 0004 refusait toute lecture de relevé scanné. La mission a changé : Cédric
demande explicitement de partir d'un PDF ou d'une photo. Nous ne renversons pas
0004, nous en réduisons la portée. Sa règle devient la voie préférée, la
transcription devient la voie de repli, et le choix entre les deux se fait
**par mandat**, sur un critère unique : Savacom a-t-elle accès à l'e-banking de
ce compte, oui ou non.

## Pourquoi

Le raisonnement de 0004 tient toujours, et la recherche sur les formats l'a
renforcé plutôt qu'affaibli : la BCN publie ses relevés en PDF, camt.053, MT940
**et** CSV ; la BCF en camt.052, camt.053, camt.054 et pain.001. Les montants
existent sous forme structurée chez les deux banques. Les reconstituer par
reconnaissance optique reste un travail contre soi-même, et le seul chemin où
un chiffre peut être inventé.

Mais 0004 supposait un accès que Savacom n'a pas toujours. Une fiduciaire reçoit
les pièces de ses mandants : quand le client envoie un PDF de son relevé, il n'y
a pas d'e-banking à ouvrir. La transcription n'est alors pas un raccourci
paresseux, c'est la seule entrée qui existe.

Confondre les deux situations mène à deux erreurs symétriques : océriser un
compte auquel on a accès, ou déclarer la mission impossible pour un compte
auquel on n'en a pas.

## Conséquences

- La question à poser par mandat, avant toute autre : **qui télécharge le
  relevé ?** Savacom depuis l'e-banking, ou le client qui l'envoie ?
- Là où l'accès existe, aucune skill n'est nécessaire : le fichier de la banque
  se charge directement. Le volume réel du travail de transcription dépend donc
  du nombre de mandats sans accès, qui n'est pas connu.
- Là où l'accès n'existe pas, tous les contrôles arithmétiques de la skill sont
  obligatoires et non contournables : ils sont la seule chose qui distingue une
  transcription d'une invention.
- L'ADR 0004 n'est pas abrogé. Sa règle reste la bonne quand elle s'applique.
