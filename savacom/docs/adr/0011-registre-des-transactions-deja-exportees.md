# Un registre des transactions déjà exportées protège des imports chevauchants

Le pipeline tient, par mandat, un registre des numéros de transaction bancaires
déjà sortis vers WinBiz, et écarte ce qu'il a déjà vu. Le registre vit sur le
NAS, à côté de la table des mandats (ADR 0009).

## Pourquoi

Le comptable retéléchargera un export dont la période chevauche la précédente :
c'est le geste le plus naturel du monde. Sans garde-fou, les mêmes écritures
partent deux fois, et un doublon comptable se détecte tard et se corrige mal.

La documentation Winbiz indique que « pour éviter les doublons, les écritures
sont renumérotées à l'importation ». Lu vite, cela laisse croire que Winbiz
détecte les doublons. Il n'en est rien : le mécanisme porte sur la numérotation
des écritures, pas sur le contenu. Rien ne protège d'un import chevauchant.

Filtrer par période reposerait sur la vigilance humaine à chaque exécution,
donc échouerait un jour.

## Conséquences

- Le numéro de transaction bancaire devient une donnée porteuse et doit rester
  intègre de bout en bout. Si l'écran d'importation Winbiz impose d'occuper la
  colonne Pièce par la référence QR, le registre devra conserver sa clé
  ailleurs — la tension est réelle et se tranche sur place.
