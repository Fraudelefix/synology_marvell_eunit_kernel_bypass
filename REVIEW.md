# Revue technique — deux passes locales

Revue effectuée par le même assistant, pas par un auditeur indépendant.

## Première passe : mutation et concurrence

Lecture des sources Synology 90080 : `drivers/ata/libata-scsi.c`
(`ata_scsi_user_scan`, `ata_scsi_hotplug`, `ata_scsi_scan_host`),
`drivers/ata/libata-eh.c` (`ata_eh_schedule_probe`, `ata_port_schedule_eh`),
`drivers/ata/libata-pmp.c`, et `include/linux/libata.h`.

La requête probe_mask=ATA_ALL_DEVICES / action|=ATA_EH_RESET est celle du scan
libata. La v2 ne l'applique qu'au lien hôte du port cible, sans PMP attaché.
Le moteur libata reste propriétaire du travail asynchrone après déchargement du
module. Aucun callback ni pointeur vers le module n'est installé dans le pilote.

Les accès sont protégés par le verrou de périphérique PCI, le mutex de scan du
port, le mutex EH de l'hôte puis son spinlock. Les acquisitions des mutex sont
non bloquantes ; aucun appel ata_port_wait_eh n'est fait sous ces verrous.
La v2 refuse les opérations EH/PM en cours, les commandes actives, les liens PMP
existants avant application, les disques ATA actifs et les périphériques SCSI
non virtuels. Elle accepte uniquement le périphérique SCSI de contrôle de type
PROCESSOR, canal 15, cible/lun 0, en l'absence de disque actif sur le lien hôte.

L'identité est celle mémorisée par le pilote après détection initiale : DX213,
EMID=0, 1095:3726, cinq ou six ports bruts de puce (correction 0.2.2). Les deux seules baies de données admises
pour READY sont les liens 0 et 1. La présence de cinq ports dans la puce ne signifie
pas que le DX213 possède cinq baies.

Ajout de gardes sur les états PMP_PMCTL et SYNO_DS_WAKING pendant la revue.
Les tests valident que les flags des trois autres ports restent inchangés,
que les verrous/références sont rendus et qu'aucun reprobe ne part sur refus.
Cela ne simule pas les effets électriques, le firmware, ni toutes les courses.

## Deuxième passe : installation et ordre de démarrage

Point d'insertion déterminé à partir des fichiers fournis par l'utilisateur :
`boot-layout.txt` et `dx213-boot-scripts.tar.gz`, et non d'une supposition sur le
Planificateur de tâches. La séquence observée place l'assemblage des groupes de
données dans `syno-space.service`, puis les services vspace et volume.
Le root système md0 existe nécessairement avant ce service : « pré-stockage »
signifie ici avant assemblage des groupes de données, pas avant tout accès SATA.

L'unité custom est appelée par Wants+After dans un drop-in de syno-space, et
ordonnée après systemd-udev-trigger. Les scripts DSM existants sont inchangés.
Le contrôle des ensembles md2+ et des montages refuse un lancement trop tardif.
L'ordre effectif et les éventuels événements udev anticipés doivent encore être
vérifiés au démarrage réel. Une directive Before seule n'aurait pas suffi à lancer
le service : le drop-in fournit explicitement Wants.

Le paquet est installé sur le système racine. Aucun fichier de /volume1 ou
/volume2 n'est requis pour lancer le service. Le script d'installation impose un
probe connecté réussi dans la même session avant stage ; stage reste désarmé.
La commande arm est distincte, sans démarrage immédiat ni reboot. Un stage
interrompu supprime ses propres fichiers systemd et conserve des fichiers inertes.
Le retrait refuse d'effacer une unité modifiée depuis l'installation.

Les tests du runner et de l'installation utilisent des copies aux chemins
réécrits dans un répertoire temporaire, avec insmod/rmmod/systemctl simulés.
Ils ne prouvent pas le comportement de systemd 219 sur DSM. Cette revue précède les essais matériels réussis décrits dans VALIDATION.md.

## Critères définis avant les essais matériels

1. Après boot connecté non modifié, inspection état 2 et identité attendue.
2. Probe manuel connecté : READY, disque SCSI publié, pas d'erreur sur les ports internes.
3. Après activation : READY avant syno-space, groupe assemblé, volume monté par DSM.
4. Intégrité en lecture après reboot ; stabilité au repos et en transfert.
5. Arrêt propre et redémarrages répétés, puis désactivation testée.

Les résultats matériels ultérieurs de ces étapes sont consignés dans VALIDATION.md. L'incident
précédent de bip/arrêt bloqué n'a pas de cause démontrée et n'est pas corrigé ici.

## Régression 0.2.2

Le diagnostic réel a confirmé le cas six ports GSCR / cinq liens attachés.
La garde précédente confondait ces deux nombres. Correction limitée à cette
comparaison ; ni les verrous, ni les commandes, ni l'installation ne changent.
Tests ajoutés : snapshot du cas réel vers READY, état admissible et application
avant attachement avec six ports bruts, refus de sept ports bruts et refus de
six liens attachés. Validation sur le NAS encore nécessaire.
