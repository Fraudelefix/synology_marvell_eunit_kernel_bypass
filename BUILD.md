# Reproduction de la compilation

Compilation réalisée le 17 octobre 2026, hors NAS, avec la chaîne officielle
Synology GCC 12.2.0 Gemini Lake et les sources Linux 4.4.x du build 90080.

Sources :
- https://global.synologydownload.com/download/ToolChain/Synology%20NAS%20GPL%20Source/7.4-90080/geminilake/linux-4.4.x.txz
- https://global.synologydownload.com/download/ToolChain/toolchain/7.4-90080/Intel%20x86%20Linux%204.4.302%20%28GeminiLake%29/geminilake-gcc1220_glibc236_x86_64-GPL.txz

SHA256 des archives :
- source : `b95d1e340b6f135fbbde7044cc93b84b1cd6e55b648954d1c3007cfd97a5cddc`
- toolchain : `d8e137040ef9cad1748e7963250768defe0fcdca69b7370c6b9be232a5b2ff10`
- configuration geminilake : `ac63364abfd3712db6fa2d5da862295338903ff1cb7c38a4d5a86aedcb51de9a`

Sur Linux de développement avec make, compilateur hôte, bc et dépendances de
préparation du noyau, dans une arborescence source dédiée (le script la modifie) :

```bash
KDIR=/chemin/linux-4.4.x \
CROSS_COMPILE=/chemin/x86_64-pc-linux-gnu/bin/x86_64-pc-linux-gnu- \
sh build.sh
bash tests/run-tests.sh
```

Ne pas compiler sur le NAS ni remplacer le fichier distribué après vérification
sans régénérer et revoir les sommes de contrôle. Le module n'est pas signé ; il
peut tainter le noyau. Aucun contournement d'une exigence de signature n'est inclus.

Les exports `firmware-exports.symvers` et la garde de 193 octets proviennent du
travail v1 sur le noyau officiel. Ils ont été conservés, non réextraits lors de
cette compilation v2. `verify-firmware.py` permet de refaire cette vérification
sur l'ELF exact SHA256
`13dcb67c60a18b363d275a80adeab6dfe4ca3ce03a314bd3acf58eb54fe03637`.
Le contrôle au chargement compare aussi les octets et l'adresse de la fonction.

Le noyau n'utilise pas CONFIG_MODVERSIONS : les CRC nuls de la table d'exports
correspondent à cette configuration. Les symboles importés par le module sont
comparés à cette table dans `binary-check.txt`. Les gardes BUILD_BUG_ON contrôlent
les offsets hérités vérifiés en v1 ; elles ne constituent pas une vérification
indépendante de chaque nouveau champ accédé en v2.

`build-log.txt` contient la dernière compilation. `test-results.txt` contient les
tests C avec ASan/UBSan, les tests shell sur fichiers et commandes simulés et les
contrôles de syntaxe. Voir VALIDATION.md pour les essais matériels ultérieurs.
Les chemins locaux du journal de compilation sont remplacés par <module-source>.
