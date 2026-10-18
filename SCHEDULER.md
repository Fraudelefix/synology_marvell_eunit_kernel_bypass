# Expérience : Planificateur de tâches DSM

**Mise à jour après essais :** la détection seule fonctionne, mais DSM ne remonte
pas spontanément le groupe dans les deux essais observés. Le complément
[preview2 / assemblage ciblé](ASSEMBLY.md) ajoute cette étape, sans modifier
l'installation de détection. Sa validation matérielle est encore à effectuer.

Version de branche : **0.3.0-scheduler-preview1**. Module inchangé : **0.2.2**.
Cette variante est testée par simulation uniquement, pas encore sur le NAS.
`main` conserve l'intégration pré-stockage déjà essayée sur le matériel.

## Ce que cet essai vérifie

Une tâche DSM « Démarrage » lance la détection après le lancement du planificateur.
Elle ne garantit pas une exécution avant l'assemblage des groupes de stockage.
Le mode `scheduled` accepte les volumes internes déjà montés, tout en conservant
les contrôles du module sur le contrôleur, le port eSATA et les activités en cours.

- Si le DX213 est déjà prêt, inspection seulement : aucune redétection.
- Sinon, au maximum une tentative de modification par démarrage, sous le même
  verrou que les autres modes du runner ; les gardes du module restent actives.
- Un service pré-stockage armé, actif ou en cours de lancement entraîne un refus.
- Aucun assemblage forcé, montage, réparation, arrêt de service de stockage,
  détachement ou réinitialisation globale du contrôleur.
- `DETECTION_RESULT=0` signifie que la tâche de détection s'est terminée sans
  erreur ; un DX213 absent est aussi un cas sans modification. Ce résultat ne
  certifie **jamais** que le volume est monté. Lire `READY`/`ALREADY_READY` et DSM.

**Limite à valider :** DSM peut laisser le groupe externe hors ligne après cette
détection tardive. Dans ce cas, cette variante n'est pas encore une solution de
montage automatique. Il faudra examiner le mécanisme DSM d'assemblage ciblé.
Les scripts de démarrage fournis par le NAS utilisent notamment
`spacetool.shared --bootup-assemble` et `synovspace -stage-load` ; ils ne prouvent
pas que ces opérations globales soient adaptées à un système déjà en service.
Cette branche ne les appelle donc pas.

## Installer sans toucher au fonctionnement actuel

Les restrictions matérielles et les prérequis du README restent applicables :
DS920+, DSM 90080 exact, DTB DX213 présent et disques de test uniquement.

[Télécharger cette branche](https://github.com/Fraudelefix/synology_marvell_eunit_kernel_bypass/archive/refs/heads/experimental/dsm-task-scheduler.zip).
Extraire sur le volume **interne**. Depuis le dossier extrait :

```bash
sha256sum -c SHA256SUMS
sudo bash install-scheduler.sh stage --isolated-test
```

Cela copie le paquet dans `/usr/local/lib/dx213-scheduler`, sur la partition
système, avec accès en écriture réservé à root. Aucun service ni tâche n'est créé
ou lancé. Une destination existante est refusée. Ne pas utiliser l'installateur
pré-stockage `install.sh stage` pour cette variante.

## Préparer la tâche dans DSM

Panneau de configuration → Planificateur de tâches → Créer → Tâche déclenchée →
Script défini par l'utilisateur. Nom : `DX213 - detection experimentale`.
Utilisateur : **root**. Événement : **Démarrage**. Laisser la tâche désactivée
pendant sa préparation. Commande, sans `sudo` et sans `&` :

```bash
/bin/bash /usr/local/lib/dx213-scheduler/scheduler.sh --isolated-test
```

Ne pas programmer une répétition périodique. La journalisation est explicite dans
`/var/log/dx213-scheduler.log`, indépendamment du dossier courant de la tâche.
Documentation DSM :
[Planificateur de tâches](https://kb.synology.com/en-uk/DSM/help/DSM/AdminCenter/system_taskscheduler).

## Basculer pour UN essai de démarrage

Une fois prêt à faire le test et après la fin des transferts : désarmer
l'intégration pré-stockage existante (sans désinstaller ses fichiers) :

```bash
sudo bash /usr/local/lib/dx213-v2/install.sh disarm
```

Activer la nouvelle tâche, puis redémarrer proprement DSM avec le DX213 connecté
et alimenté. Ne pas cliquer sur « Exécuter » avant ce redémarrage : l'ancien
service peut encore être actif et le flag déjà modifié fausserait l'essai.
Ne pas réarmer l'ancien service en même temps que cette tâche.

Après le démarrage, sans assemblage manuel préalable :

```bash
sudo cat /var/log/dx213-scheduler.log
cat /proc/mdstat
df -h
sudo bash /usr/local/lib/dx213-scheduler/collect.sh > /volume1/test/dx213-scheduler-diagnostic.txt
```

Vérifier séparément : détection READY ; groupe externe actif ; volume externe
monté ; puis relecture du fichier de test avec comparaison SHA256. Le journal
de la tâche et le diagnostic peuvent contenir des informations privées.
Si le groupe reste hors ligne, conserver ce constat avant toute action manuelle.
Ne pas initialiser ou recréer le groupe existant.

Le marqueur `/run/dx213-scheduler-attempt` empêche une deuxième tentative de
modification dans le même démarrage, même après un échec. Ne pas le supprimer
pour forcer un nouvel essai. Le verrou `/run/dx213-v2.lock` reste partagé.
Une commande noyau bloquée peut dépasser les délais utilisateurs : la branche
ne promet pas un arrêt garanti face à un blocage du pilote.

## Revenir au fonctionnement pré-stockage validé

1. Désactiver la tâche DSM.
2. Réarmer l'installation d'origine conservée :

```bash
sudo bash /usr/local/lib/dx213-v2/install.sh arm --isolated-test
```

3. Redémarrer proprement DSM, puis vérifier `/var/log/dx213-v2.log` et les volumes.

La désactivation d'une tâche ne stoppe pas une exécution déjà en cours et ne
restaure pas le flag mémoire. Les fichiers de cette variante peuvent rester
installés et inactifs. L'installation pré-stockage d'origine n'est pas modifiée.
