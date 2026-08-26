# Aucun format de sortie n'est construit avant de savoir ce qu'AE Pro Easy accepte

Deux cibles sont possibles pour le fichier que produit la transcription : le CSV
propre à chaque banque, ou le camt.053. Nous n'en construisons aucune tant que
l'écran d'import d'AE Pro Easy n'a pas été regardé. Et si les deux sont
acceptées, c'est le camt.053 qui l'emporte.

## Pourquoi

L'état du marché suisse ne tranche pas la question, parce que ce n'est pas la
question. Ce qui décide, c'est ce que le logiciel destinataire avale — pas ce
que les banques produisent le mieux.

Les indices penchent vers le CSV. AE Pro Easy affiche « Le fichier semble être
un extrait Raiffeisen, mais la banque sélectionnée est BCN » : il reconnaît une
banque à la **forme** du fichier. Un lecteur de camt.053 n'aurait pas besoin de
deviner — le camt porte l'IBAN et le BIC en clair. Ce message décrit le
comportement d'un détecteur de format CSV.

Mais l'indice n'est pas une preuve : rien n'interdit au logiciel d'offrir les
deux entrées. Personne n'a encore regardé.

À acceptation égale, le camt.053 gagne sur trois points mesurables :

1. **Il est spécifié.** Schéma XML public, versionné, avec des règles suisses
   officielles (SIX). Le CSV bancaire ne l'est pas : Banana Comptabilité écrit
   textuellement que « le format .csv est différent pour chaque banque et est
   mis à jour et modifié régulièrement ». Bâtir sur lui, c'est bâtir sur un
   format que la banque peut changer sans préavis et sans recours.
2. **Un seul générateur couvre les quatre banques.** L'identité de la banque
   vit dans des champs, pas dans la forme du fichier. Quatre fichiers de format
   à rétro-concevoir deviennent un schéma à respecter.
3. **Il existe là où le CSV n'existe peut-être pas.** La BCF documente
   camt.052, camt.053, camt.054 et pain.001, et ne mentionne le CSV nulle part.
   L'existence même d'un export CSV BCF n'est attestée par aucune source
   publique.

Le CSV garde un avantage, et il n'est pas mince : un camt.053 exige des champs
qu'un relevé imprimé ne porte pas — identifiants de message, de relevé, de
séquence, références d'écriture. Certains se fabriquent, d'autres non. Ce coût
ne se chiffre qu'une fois la cible connue.

## Conséquences

- Une capture de l'écran d'import d'AE Pro Easy débloque la décision. C'est la
  même capture qui manque depuis le début de la mission.
- Les formats `bcn.json` et `bcf.json` restent à `a_completer`, et le script
  refuse d'écrire avec. Ce n'est plus un manque d'information : c'est la
  conséquence assumée de cette décision.
- Si le camt.053 est retenu, la skill garde sa lecture et ses contrôles
  arithmétiques intacts — seule l'étape d'écriture change. C'est la raison pour
  laquelle lecture, vérification et écriture ont été séparées dès le départ.
