# Planificateur DSM : assemblage ciblé, preview2

Complément expérimental à `0.3.0-scheduler-preview1`. Aucun changement du module
noyau ni du paquet de détection déjà installé. Pas encore validé sur le NAS.

Les essais matériels du 18 octobre ont confirmé que la tâche détecte le disque
mais ne remonte pas spontanément le groupe, même après un redémarrage propre.
Une capture de l'interface DSM a identifié l'appel `SYNO.Storage.CGI.Pool`,
`method=reassemble`, `version=1`, `space_uuid=<UUID du groupe>`, `force=false`.
L'inventaire local `SYNO.Storage.CGI.Storage/load_info` a été validé via
`/usr/syno/bin/synowebapi --exec`, exécuté comme root sans session navigateur.
L'appel local de mutation reste à tester ; sa réussite dans l'interface ne
garantit pas sa réussite locale.

## Portée et protections

Uniquement DSM 90080 exact, DS920+, DX213-1 baie 1, groupe SHR à un disque sans
protection, un composant MD et un volume non chiffré. Disques de test uniquement.
Le groupe est enregistré localement pendant qu'il est sain et monté. Identités
enregistrées : UUID du groupe et du volume, modèle et numéro de série du disque,
identifiant du groupe, chemin MD et point de montage. Aucune identité réelle
ni information d'authentification n'est incluse dans le dépôt.

Avant l'action, le complément vérifie l'inventaire DSM, l'absence de disques
manquants, l'appartenance à l'eSATA `ata6/host5`, l'absence d'opération concurrente
signalée par DSM et l'autorisation `can_assemble=true`. Il refuse les schémas
inconnus. Un groupe déjà normal et monté ne reçoit aucune demande. Une opération
déjà en cours est seulement observée. Le succès final exige un montage `rw`
dont les dépendances sysfs passent par le MD enregistré et le disque eSATA.

Une seule demande par démarrage via `/run/dx213-assembly-attempt`, conservé même
en cas d'échec. Verrou partagé `/run/dx213-v2.lock`. Pas de `mdadm --force`, pas
d'appel global de démarrage du stockage, pas de réparation, démontage ou rollback.
Chaque appel API a un délai de 45 s ; après acceptation, observation pendant
environ trois minutes. Une opération DSM peut continuer après l'expiration du
délai client. Ne pas supprimer les marqueurs/verrous pour forcer un nouvel essai.
Les vérifications réduisent les risques mais ne rendent pas la séquence atomique
avec les actions lancées depuis DSM : ne pas gérer le stockage en parallèle.

## Installation du complément

Désactiver temporairement la tâche DSM. Laisser le groupe DX213 assemblé et le
volume monté. Garder l'ancien service pré-stockage désarmé. Depuis le nouveau ZIP
de cette branche, extrait dans un **nouveau dossier**, exécuter :

```bash
sha256sum -c SHA256SUMS &&
sudo bash install-assembly.sh --isolated-test
```

Cela installe seulement `/usr/local/lib/dx213-assembly`. Le dossier et la commande
de détection précédents restent inchangés. Le complément refuse une destination
existante ; pas de mise à jour automatique.

Enregistrer le groupe sain avec son UUID, relevé dans `load_info` (pas celui du
volume ni du groupe interne). Remplacer `UUID_DU_GROUPE_DX213` :

```bash
sudo /bin/python3 /usr/local/lib/dx213-assembly/assemble.py enroll \
  --pool-uuid UUID_DU_GROUPE_DX213 --isolated-test
sudo /bin/python3 /usr/local/lib/dx213-assembly/assemble.py inspect
```

Résultats attendus : `ENROLLED` puis `state=ready mounted=True`. L'enregistrement
écrit seulement `target.json` dans le dossier root ; il ne lance pas d'assemblage.
Ne pas publier ce fichier : il contient les identifiants propres au NAS.

## Essai au démarrage

Dans la tâche DSM existante (root, Démarrage), remplacer la commande par :

```bash
/bin/bash /usr/local/lib/dx213-assembly/task.sh --isolated-test
```

Réactiver la tâche. Garder l'hibernation désactivée pendant cet essai, terminer
les transferts puis redémarrer proprement avec le DX213 connecté. Après quelques
minutes, sans assemblage manuel :

```bash
sudo tail -n 100 /var/log/dx213-scheduler.log
cat /proc/mdstat
df -h
```

Attendre `MOUNT_READY` et `ASSEMBLY_RESULT=0`, puis vérifier le fichier de test
par SHA256. Une absence d'erreur de détection ne suffit pas à valider le montage.
En cas de refus, conserver le journal avant toute nouvelle opération manuelle.

## Retour à la détection seule

Désactiver la tâche, remettre sa commande précédente :
`/bin/bash /usr/local/lib/dx213-scheduler/scheduler.sh --isolated-test`.
Les fichiers du complément peuvent rester inactifs. Aucune action sur les volumes
montés n'est effectuée par ce changement. Pour revenir au service pré-stockage,
suivre SCHEDULER.md et ne jamais activer les deux modes simultanément.

## Incident de stabilité non résolu

Le 18 octobre, avec la version pré-stockage, le disque interne sur ata4 a disparu
après une sortie de veille profonde ; md0/md1/md2 ont perdu leur unique membre,
et DSM est devenu inaccessible. L'arrêt a dû être forcé, puis le NAS a redémarré
sans le DX213. La cause n'est pas établie : un effet du contournement sur le
contrôleur partagé ne peut pas être exclu. Désactiver l'hibernation pour cet essai
ne constitue pas une correction prouvée. Ne pas utiliser sur les disques de production.
