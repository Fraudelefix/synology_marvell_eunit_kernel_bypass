# Validation matérielle — état au 18 octobre 2026

Périmètre : un DS920+ Marvell 88SE9235, DSM 7.4.1-90080, installation isolée
sur un disque interne de test, un disque de test dans la première baie du DX213.
Les disques de production avaient été retirés. Les M.2 n'ont pas été utilisés
comme cible de test. Aucun numéro de série, adresse locale ou journal brut publié.

| Essai | Résultat observé |
|---|---|
| v1 : retrait du flag avec eSATA débranché puis reconnexion | Disque externe détecté |
| Écriture de 4 Gio, fsync puis relecture directe et SHA256 | Empreintes identiques |
| 0.2.2 : probe avec câble déjà connecté | READY, disque détecté sans débranchement |
| Assemblage manuel après ce probe | Groupe externe et volume disponibles |
| Paquet 0.2.3 : arrêt complet puis rallumage connecté | Détection, assemblage et montage automatiques |
| Redémarrage depuis DSM, connecté | Même résultat automatique |
| Relecture directe des mêmes 4 Gio après redémarrage | SHA256 identique à la source, environ 128 Mo/s |

Chronologie du démarrage du 18 octobre : requête du module vers 37 s, état READY
vers 56 s, assemblage des groupes de données vers 57 s. L'ordre systemd constaté
place le service avant syno-space.service. Les deux volumes sont montés rw.

La restriction du noyau d'origine est visible avant le service ; le bit 0x8 est
retiré, la liaison revient à 3 Gbit/s et le disque est publié. Des erreurs de
lecture GSCR[30/31] restent visibles pendant la détection. Elles n'ont pas empêché
ces essais, mais leur présence n'est pas une preuve d'innocuité générale.

## Incidents non expliqués et limites

- Un incident au repos avec bip et arrêt bloqué a nécessité un arrêt forcé.
- Un redémarrage ultérieur, avant activation du service, a présenté « Aucun disque
  détecté » et refusé SSH. Un arrêt complet puis démarrage sans DX213 a récupéré
  le système. Deux paramètres ont changé à la fois : cause non déterminée.
- Le succès des deux démarrages suivants n'explique pas ces incidents.
- Deux disques simultanés dans le DX213, autres modèles/révisions, autres builds
  DSM, arrêt/réveil d'hibernation, longues charges mixtes et usage de production
  ne sont pas validés.
- Les durées et débits sont des observations d'un essai, pas des garanties.
- Si un démarrage échoue avant montage de md0, le service stocké sur md0 ne peut
  pas intervenir assez tôt pour corriger cet échec.

Le paquet est expérimental. Aucun changement de statut vers « stable » ne découle
seulement de ces essais. Les tests logiciels et la revue locale ne constituent
pas un audit indépendant.
