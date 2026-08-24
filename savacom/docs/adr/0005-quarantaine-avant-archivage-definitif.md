# Une pièce passe par une quarantaine avant son dossier définitif sur le NAS

Le fichier d'import porte le chemin NAS définitif de la pièce. Plutôt que de
déplacer la pièce avant l'import — ou après — nous la renommons et la déposons
dans une zone de quarantaine, puis la promouvons vers son dossier définitif une
fois l'import confirmé.

## Pourquoi

C'est la seule séquence où aucun état intermédiaire n'est faux. Déplacer avant
laisse des pièces archivées sans écriture si l'import échoue ; déplacer après
laisse un chemin inscrit dans le fichier d'import qui pointe vers un fichier
absent.

## Conséquences

- Le processus devient reprenable : après une interruption, ce qui reste en
  quarantaine est exactement ce qui reste à traiter.
- Sans cette étape, une interruption au mauvais moment laisse un mélange
  indémêlable de pièces archivées et non comptabilisées, à trier à la main.
