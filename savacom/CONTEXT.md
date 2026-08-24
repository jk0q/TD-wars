# Savacom — flux comptables

Savacom Sàrl est une fiduciaire neuchâteloise. Ce contexte couvre la chaîne qui
va des pièces reçues (relevés bancaires, factures fournisseurs) jusqu'aux
écritures importées dans WinBiz et aux justificatifs archivés sur le NAS.

## Langue

### Acteurs et périmètre

**Mandat** :
Une société cliente dont Savacom tient la comptabilité. Chaque mandat a son
propre dossier WinBiz, son plan comptable, sa banque et son dossier NAS.
_Éviter_ : client, dossier, société — trop ambigus, « client » désignant aussi
les clients du mandat.

**Pièce** :
Un document justificatif reçu : relevé bancaire, facture fournisseur, ticket.
_Éviter_ : document, justificatif, fichier.

### Fichiers — trois choses différentes appelées « CSV »

**Export bancaire** :
Fichier produit par la banque ou son e-banking, décrivant les mouvements d'un
compte. Son format appartient à la banque et varie d'un canal à l'autre pour
une même banque.
_Éviter_ : relevé, fichier bancaire.

**Relevé** :
Représentation lisible par un humain d'un export bancaire — PDF ou papier
scanné. Contient les mêmes mouvements, mais appauvris : le scan BCN a perdu les
références de paiement.
_Éviter_ : extrait, statement.

**Fichier d'import** :
Fichier attendu par WinBiz pour créer des écritures. Format imposé par WinBiz,
jamais par la banque. C'est la cible de toute conversion.
_Éviter_ : CSV WinBiz, fichier de sortie.

### Structure d'un export bancaire

**Ligne mère** :
Ligne portant un mouvement réel du compte : une date, un montant, un solde.
Une ligne mère donne exactement une écriture.

**Sous-ligne** :
Ligne sans date, rattachée à la ligne mère qui la précède. Elle détaille un
mouvement sans en être un. Une sous-ligne ne donne jamais d'écriture.
_Éviter_ : ligne de continuation, ligne de détail.

**Versement collectif** :
Ligne mère dont le montant regroupe plusieurs paiements distincts, chacun
décrit par une sous-ligne portant sa propre référence QR.
_Éviter_ : paiement groupé, crédit multiple.

**Référence QR** :
Identifiant structuré (`QRR:`) rattaché à un encaissement, qui désigne la
facture débiteur payée. Présent dans l'export e-banking, absent des exports
appauvris et des relevés scannés.
_Éviter_ : référence de paiement, QRR.

### Comptabilisation

**Écriture** :
Une opération en partie double : une date, un compte débité, un compte
crédité, un libellé, un montant positif. Le sens de l'opération est porté par
les comptes, jamais par le signe du montant.

**Compte d'attente** :
Compte de contrepartie provisoire, porté par toute écriture dont l'imputation
n'a pas été décidée. Une écriture sur compte d'attente est un travail annoncé,
pas une erreur.
_Éviter_ : compte transitoire, compte 9999.

**Imputation** :
La décision d'attribuer un compte de charge ou de produit à une écriture. Une
décision comptable, prise par un humain — jamais une transformation de données.
_Éviter_ : affectation, mapping comptable.

**Rapprochement** :
L'appariement d'un encaissement avec la facture débiteur qu'il solde, via sa
référence QR. Distinct de l'imputation : le rapprochement identifie *qui* a
payé, l'imputation décide *quel compte* mouvementer.
_Éviter_ : lettrage, matching.

### Contrôles

**Invariante** :
Règle vraie indépendamment de tout code que nous écrivons, servant à juger une
conversion. Exemple : la chaîne des soldes d'un export bancaire.
_Éviter_ : contrôle, validation, check.

**Anomalie bloquante** :
Violation d'une invariante. Interdit la production d'un fichier d'import : un
fichier silencieusement faux est pire qu'une conversion qui échoue.
_Éviter_ : erreur, warning.
