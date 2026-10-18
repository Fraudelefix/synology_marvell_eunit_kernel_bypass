# Changelog

## 0.3.0-scheduler-preview2 — separate assembly helper

- Preserve the installed detection package and kernel module unchanged.
- Add a separately installed, locally enrolled single-disk DX213 assembly helper.
- Use the observed DSM reassemble API with exact pool UUID and force=false.
- Verify inventory identity, admissible state, eSATA topology and mount ancestry.
- Add sanitized fixtures from observed normal/missing DSM inventories and tests.
- Hardware validation of local reassembly pending; sleep/wake incident unresolved.

## 0.3.0-scheduler-preview1 — experimental branch only

- Add a separate root-filesystem installer and DSM Task Scheduler entry point.
- Reuse the unchanged 0.2.2 kernel module with a late-detection runner mode.
- Refuse armed/active pre-storage integration; retain the shared runner lock.
- Inspect an already-ready target without reprobe; permit at most one scheduled
  mutation attempt per boot, retaining the attempt marker after failure.
- No automatic pool assembly or mounting: this remains a hardware experiment.
- Add 15 scheduler runner cases and 6 staging tests. No hardware validation yet.

## 0.2.3 — 2026-10-18, publication préparée

- Installateur : comparaison du contenu des identifiants de démarrage au lieu
  de cmp -s directement sur procfs, dont la taille déclarée pouvait donner un
  faux refus.
- Module 0.2.2 conservé octet pour octet.
- Documentation des essais matériels réussis et des incidents non expliqués.
- Préparation du dépôt, licence, outil de sommes de contrôle et consignes de rapport.

## 0.2.2 — 2026-10-17

- Garde DX213 : distinction entre cinq/six ports GSCR bruts et cinq liens attachés.
- Tests de régression et conservation des instantanés détaillés.

## 0.2.1 — 2026-10-17

- Diagnostic des ports bruts, liens attachés, identifiants PMP et motif du refus.

## 0.2 — 2026-10-17

- Redétection ciblée avec câble connecté, service pré-assemblage, installation,
  activation séparée et retrait de l'intégration systemd.

## 0.1 — expérimentation initiale

- Modification du flag du port eSATA uniquement à PHY déconnecté.
