# Les encaissements partent sur un compte d'attente ; la référence QR est préservée intacte

Cent-deux encaissements de l'export UBS portent une référence QR désignant une
facture débiteur précise. Plutôt que de rapprocher automatiquement ces
encaissements des factures ouvertes dans WinBiz — ce que faisait Multigest —
nous les portons sur un compte d'attente, en transportant la référence QR
jusqu'à l'écriture. Le lettrage reste manuel.

## Pourquoi

Le rapprochement automatique impliquerait de lire le grand livre débiteurs de
WinBiz : nouvelle source, nouveaux droits, nouveau risque — et le brief demande
explicitement de *sortir* de l'extraction SQL de la base WinBiz.

## Conséquences

- La référence QR doit voyager intacte de l'export jusqu'à l'écriture. C'est
  bon marché aujourd'hui et très cher à rattraper : sans elle, le rapprochement
  automatique deviendrait impossible sans reprendre tout l'historique.
- Le rapprochement automatique reste ouvert comme évolution, sans dette.
