# La table IBAN vers mandat vit sur le NAS et appartient au comptable

La table qui rattache chaque IBAN à son mandat est un fichier unique, stocké sur
le NAS à un emplacement stable, édité par le comptable lui-même. Elle n'est ni
versionnée chez l'intégrateur, ni déduite de l'arborescence des dossiers.

## Pourquoi

La fiduciaire prend et perd des mandats sans prévenir son prestataire. Si la
table vit chez l'intégrateur, chaque nouveau mandat devient un ticket, un délai
et une dépendance — exactement la situation dont le projet cherche à sortir en
quittant Multigest.

Déduire la table de l'arborescence serait élégant, mais ferait porter une
responsabilité technique à une structure de dossiers que quelqu'un réorganisera
un jour sans savoir ce qu'il casse.

## Conséquences

- Un IBAN absent de la table arrête le traitement en le nommant, plutôt que de
  poursuivre au jugé (voir ADR 0006).
