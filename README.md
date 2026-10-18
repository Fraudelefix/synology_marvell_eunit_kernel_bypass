# Synology Marvell Eunit Kernel Bypass

> **Complément preview2 : assemblage ciblé depuis le Planificateur.**
> Voir [ASSEMBLY.md](ASSEMBLY.md). La détection seule a réussi sur le NAS, mais
> le groupe reste hors ligne après un redémarrage propre. Ce complément utilise
> l'opération DSM d'assemblage en ligne ; son exécution locale reste à valider.

> **Branche expérimentale Planificateur DSM : 0.3.0-scheduler-preview1.**
> Pour essayer cette variante, suivre [SCHEDULER.md](SCHEDULER.md), pas la procédure
> d'installation pré-stockage ci-dessous. Détection tardive seulement ; montage
> automatique du volume encore à valider sur le NAS. Le module reste en 0.2.2.
> Les essais matériels décrits ci-dessous concernent la version pré-stockage.

Contournement expérimental pour utiliser un **DX213 sur un DS920+ équipé du
Marvell 88SE9235**, avec détection avant l'assemblage des groupes de stockage DSM.

**Version du paquet : 0.2.3 — module : 0.2.2.**

> Ce projet n'est ni officiel ni approuvé par Synology. Il modifie l'état du
> pilote SATA dans le noyau en mémoire. Les essais réussis concernent un seul NAS
> avec des disques de test et un seul disque dans le DX213. Ils ne garantissent
> pas la stabilité ni l'intégrité de toutes les configurations.

English summary: exact-build experimental kernel-state workaround for a DS920+
with a Marvell 88SE9235 and a DX213. Connected reprobe, automatic assembly after
cold start and DSM restart, and a 4 GiB direct-read integrity check succeeded on
one isolated test setup. Not a general compatibility patch or production release.

## Compatibilité strictement limitée

| Élément | Cible |
|---|---|
| NAS | Synology DS920+ / geminilake |
| DSM | 7.4.1, build 90080 |
| Noyau | `4.4.302+ #90080 SMP Wed Jul 22 00:08:29 CST 2026` |
| Contrôleur SATA | Marvell `1b4b:9235`, PCI `0000:01:00.0` |
| Port cible | Port 3 du contrôleur, `ata6`, hôte SCSI 5 |
| Extension | DX213, PMP Silicon Image `1095:3726`, EMID 0 |

Le modèle, le noyau et une empreinte du code noyau sont contrôlés avant toute
opération. **Ne pas supprimer ces gardes pour accepter une autre version.**
Une mise à jour DSM peut rendre le module inutilisable et le volume externe absent.

## Principe

Le pilote Synology refuse certaines extensions SATA 3 Gbit/s derrière le
Marvell 88SE9235. Le module retire le bit `SYNO_STATUS_IS_MV9235` uniquement du
lien eSATA visé, après vérification de son identité et de son état. Il demande
ensuite une redétection de ce port au mécanisme de récupération libata.

Il ne réécrit pas les instructions du noyau, son image sur disque ou l'initramfs,
et ne désactive pas globalement le contrôleur PCI partagé avec les baies internes.
Le module est déchargé après chaque opération ; la modification mémoire reste
jusqu'au redémarrage. Aucun callback du module n'est conservé dans le pilote.

Le DX213 observé annonce **six ports bruts**, normalisés par le pilote à **cinq
liens**, pour **deux baies physiques**. La v0.2.2 corrige la confusion entre ces
nombres dans la garde d'identité.

Le service `dx213-prestorage.service` est placé avant `syno-space.service` : DSM
assemble les groupes de données après la détection du disque externe. Cela vient
après le montage de la partition système `md0`, et ne peut donc pas résoudre un
échec antérieur au chargement de cette partition.

## Prérequis

- Installation de test isolée, sauvegardes disponibles, aucun disque de production.
- Groupe du DX213 indépendant des groupes internes ; ne pas répartir un groupe
  entre le NAS et l'extension.
- Déclaration DX213 déjà présente dans le DTB. Le projet complémentaire
  [Synology_enable_eunit de 007revad](https://github.com/007revad/Synology_enable_eunit)
  fournit cette configuration. Ce module ne remplace pas cette étape.
- Au moins un disque de test dans le DX213 pour obtenir l'état READY.
- Accès SSH administrateur et Bash ; aucun besoin de compiler sur le NAS.
- Pas de tâche concurrente appliquant un ancien contournement.

Lire [VALIDATION.md](VALIDATION.md) et [REVIEW.md](REVIEW.md) avant un essai.

## Télécharger et vérifier

[Télécharger le ZIP de la branche main](https://github.com/Fraudelefix/synology_marvell_eunit_kernel_bypass/archive/refs/heads/main.zip).
Cette branche peut évoluer ; vérifier la version indiquée dans le README avant un essai.


Télécharger une version figée du dépôt ou l'archive fournie par son mainteneur.
Ne pas mélanger les fichiers de plusieurs versions. Extraire sur un volume interne,
par exemple `/volume1/test/synology_marvell_eunit_kernel_bypass-main` (dossier créé par le ZIP GitHub). Ne pas placer le paquet sur l'extension.

```bash
cd /volume1/test/synology_marvell_eunit_kernel_bypass-main
sha256sum -c SHA256SUMS
sudo bash run.sh inspect
```

Les sommes vérifient la cohérence du paquet, pas l'authenticité d'une source
compromise. Le module n'est pas signé et son chargement peut marquer le noyau
comme « tainted », y compris en mode inspection.

## Essai manuel, câble connecté

L'inspection ne modifie aucun flag et ne demande aucune redétection.
Les valeurs affichées sont décimales.

| state | Signification |
|---|---|
| 1 | Aucun périphérique PHY présent ; rien n'est modifié |
| 2 | DX213 connecté et état admissible pour un essai |
| 3 | Requête de redétection envoyée, pas encore terminée |
| 4 | Au moins un disque du DX213 est prêt |
| 5 | Pilote occupé ou détection en cours ; certaines valeurs peuvent rester à zéro |
| 6 | État refusé ; conserver le diagnostic |

Avec un DX213 connecté, au repos, refusé par le noyau d'origine et `state=2` :

```bash
sudo bash run.sh probe --isolated-test
```

Attendre `READY`. Le script refuse un port exposant déjà un périphérique bloc.
Il ne faut pas lancer une nouvelle détection sur un volume monté. Un `state=4`
lors de l'inspection indique que le disque est déjà détecté.

Après un échec, ne pas répéter en boucle ni retirer les gardes. La modification
mémoire peut subsister et le pilote peut encore travailler. Collecter les journaux :

```bash
sudo bash collect.sh > /volume1/test/dx213-diagnostic.txt
```

DSM étant déjà lancé, l'assemblage en ligne du groupe existant dans son interface
peut être nécessaire pour cet essai manuel. Ne pas créer ou initialiser un nouveau
groupe à la place d'un groupe existant.

## Installer le lancement automatique

Uniquement après un `probe` réussi **dans la même session de démarrage** :

```bash
sudo bash install.sh stage --isolated-test &&
sudo bash /usr/local/lib/dx213-v2/install.sh arm --isolated-test
```

`stage` copie le paquet sur la partition système et ajoute :

- `/etc/systemd/system/dx213-prestorage.service` ;
- `/etc/systemd/system/syno-space.service.d/90-dx213-v2.conf`.

Les scripts DSM existants ne sont pas réécrits. `arm` active les prochains
démarrages, sans démarrer le service immédiatement. Ne pas utiliser
`systemctl start` pendant que les volumes sont montés. Le Planificateur de tâches
DSM ne fournit pas ici l'ordre explicite requis avant `syno-space.service`.

Terminer les transferts, arrêter proprement DSM, attendre l'extinction complète,
puis rallumer avec le DX213 branché et alimenté. Sans assemblage manuel, vérifier :

```bash
sudo cat /var/log/dx213-v2.log
cat /proc/mdstat
df -h
```

Résultat attendu : `READY`, `result=0`, groupe externe actif et volume monté.
Les noms `cachedev_N` peuvent varier ; utiliser les points de montage des volumes.
Le service refuse un lancement tardif si un groupe de données md2+ est déjà
assemblé ou un volume de données déjà monté. La dépendance `Wants` permet à DSM
normalement de poursuivre si le service échoue, mais ne protège pas contre un
blocage du noyau lui-même.

Si la version 0.2.3 est déjà installée et fonctionne, la publication sur GitHub
ne nécessite aucune réinstallation. L'installateur refuse d'écraser une installation
existante ; cette version ne fournit pas de procédure de mise à niveau automatique.

## Désactiver / retirer

```bash
sudo bash /usr/local/lib/dx213-v2/install.sh disarm
```

Désactive les prochains lancements. Pour retirer aussi les fichiers systemd :

```bash
sudo bash /usr/local/lib/dx213-v2/install.sh uninstall
```

Les volumes en cours ne sont pas démontés. Les fichiers installés et journaux
restent disponibles ; le flag mémoire n'est pas restauré avant redémarrage.
Si DSM est inaccessible, ces commandes SSH ne sont pas un moyen de secours garanti.
Ne pas confondre désactivation du service avec réinitialisation matérielle du NAS.

## Compilation, tests et contributions

Voir [BUILD.md](BUILD.md). Les sources du module, les exports du noyau cible et
les tests sont inclus. Sur un poste Linux de développement :

```bash
bash tests/run-tests.sh
```

Les tests hôtes simulent les appels noyau ; ils ne reproduisent pas le matériel.
Après modification de fichiers, régénérer `SHA256SUMS` avec
`python3 tools/update-checksums.py` et revoir les changements avant distribution.
Ne jamais ajouter au dépôt les fichiers `connected-probe.ok`, `boot.enabled` ou
les journaux bruts d'un NAS. Ceux-ci peuvent contenir adresses, numéros de série
et autres informations personnelles.

## Origine et licence

Étude motivée par [Synology_enable_eunit, issue #41](https://github.com/007revad/Synology_enable_eunit/issues/41).
Ce dépôt est distinct du projet de 007revad et n'implique pas son approbation.
Analyse fondée sur les sources GPL Synology 90080 et validation sur une installation
de test. Code développé avec l'assistance de Codex ; revue humaine indépendante
bienvenue, en particulier pour la concurrence dans le pilote SATA.

Code de ce projet sous GPL-2.0-only ; voir [COPYING](COPYING).
Les droits sur les composants tiers restent à leurs titulaires.
