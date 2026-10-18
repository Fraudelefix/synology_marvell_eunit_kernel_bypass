#!/bin/sh
set -eu
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${KDIR:?Set KDIR to a dedicated extracted build-90080 Gemini Lake kernel source tree}"
: "${CROSS_COMPILE:?Set CROSS_COMPILE to the absolute Synology compiler prefix}"
KDIR=$(CDPATH= cd -- "$KDIR" && pwd)
expected_config=ac63364abfd3712db6fa2d5da862295338903ff1cb7c38a4d5a86aedcb51de9a
actual_config=$(sha256sum "$KDIR/synoconfigs/geminilake" | cut -d ' ' -f 1)
[ "$actual_config" = "$expected_config" ] || {
    echo 'Wrong source configuration; refusing build.' >&2; exit 1;
}
cp "$KDIR/synoconfigs/geminilake" "$KDIR/.config"
make -C "$KDIR" ARCH=x86_64 CROSS_COMPILE="$CROSS_COMPILE" LOCALVERSION=+ olddefconfig modules_prepare
grep -q '^# CONFIG_MODVERSIONS is not set$' "$KDIR/.config"
# Actual exports extracted from the exact official ELF. CRC values are zero
# because this kernel does not use CONFIG_MODVERSIONS; no CRC is being bypassed.
cp "$package_dir/firmware-exports.symvers" "$KDIR/Module.symvers"
make -C "$KDIR" ARCH=x86_64 CROSS_COMPILE="$CROSS_COMPILE" LOCALVERSION=+ M="$package_dir" modules
echo 'Build complete. Review the result before regenerating package checksums.'
