#!/bin/bash
# Explicit staging/arming only. Does not start a service or reboot.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
pkg=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dst=/usr/local/lib/dx213-v2
unit=/etc/systemd/system/dx213-prestorage.service
dropdir=/etc/systemd/system/syno-space.service.d
drop=$dropdir/90-dx213-v2.conf
cmd=${1:-help}
[[ $(id -u) = 0 ]] || { echo 'Root required'; exit 1; }
case "$cmd" in
stage)
    [[ ${2:-} = --isolated-test ]] || { echo 'stage requires --isolated-test'; exit 1; }
    [[ ! -e "$dst" && ! -L "$dst" && ! -e "$unit" && ! -L "$unit" && ! -e "$drop" && ! -L "$drop" ]] || {
        echo 'Existing installation/path: refusing overwrite'; exit 1;
    }
    [[ $(cat /proc/sys/kernel/syno_hw_version) = DS920+ ]] || exit 1
    [[ $(uname -v) = '#90080 SMP Wed Jul 22 00:08:29 CST 2026' ]] || exit 1
    cd "$pkg"
    sha256sum -c SHA256SUMS >/dev/null
    [[ -f connected-probe.ok ]] || {
        echo 'A successful manual connected probe on this boot is required before staging'; exit 1;
    }
    recorded_boot=$(cat connected-probe.ok) || exit 1
    current_boot=$(cat /proc/sys/kernel/random/boot_id) || exit 1
    [[ -n "$current_boot" && "$recorded_boot" = "$current_boot" ]] || {
        echo 'Connected probe belongs to another boot; refusing staging'; exit 1;
    }
    # Prevent a pre-volume dependency on a data volume through a symlink/mount.
    [[ -d /usr/local/lib ]] || { echo '/usr/local/lib absent'; exit 1; }
    [[ $(df -P /usr/local/lib | awk 'END {print $6}') = / ]] || {
        echo 'Install directory is not on the root filesystem'; exit 1;
    }
    [[ ! -L "$dropdir" ]] || { echo 'Drop-in directory is a symlink'; exit 1; }
    mkdir -m 700 "$dst"
    # Failed staging leaves only a disarmed directory for diagnosis.
    # Remove only files this invocation created, never another drop-in.
    made_unit=0; made_drop=0; committed=0
    stage_cleanup() {
        if [[ "$committed" = 0 ]]; then
            rm -f "$dst/boot.enabled"
            [[ "$made_drop" = 0 ]] || rm -f "$drop"
            [[ "$made_unit" = 0 ]] || rm -f "$unit"
            systemctl daemon-reload || true
            echo "Staging incomplete; inert files retained at $dst" >&2
        fi
    }
    trap stage_cleanup EXIT
    trap 'exit 130' INT TERM
    cp -a "$pkg"/. "$dst"/
    chown -R root:root "$dst"
    chmod -R go-w "$dst"
    chmod 700 "$dst/run.sh" "$dst/boot.sh"
    rm -f "$dst/boot.enabled"
    touch "$dst/.dx213-v2-owned"
    mkdir -p "$dropdir"
    made_unit=1
    cp "$dst/dx213-prestorage.service" "$unit"
    made_drop=1
    cp "$dst/prestorage.conf" "$drop"
    systemctl daemon-reload
    committed=1
    echo 'Staged DISARMED. No service started. Use arm only when ready for the boot experiment.'
    ;;
arm)
    [[ ${2:-} = --isolated-test ]] || { echo 'arm requires --isolated-test'; exit 1; }
    [[ -f "$dst/.dx213-v2-owned" ]] || exit 1
    (cd "$dst" && sha256sum -c SHA256SUMS >/dev/null)
    cmp -s "$unit" "$dst/dx213-prestorage.service" || exit 1
    cmp -s "$drop" "$dst/prestorage.conf" || exit 1
    touch "$dst/boot.enabled"
    echo 'Armed for NEXT BOOT only. No start or reboot performed.'
    ;;
disarm)
    [[ -f "$dst/.dx213-v2-owned" ]] || exit 1
    rm -f "$dst/boot.enabled"
    echo 'Disarmed for future boots. Current driver state is unchanged.'
    ;;
uninstall)
    [[ -f "$dst/.dx213-v2-owned" ]] || exit 1
    rm -f "$dst/boot.enabled"
    [[ ! -e "$unit" ]] || cmp -s "$unit" "$dst/dx213-prestorage.service" || { echo 'Unit changed; refusing deletion'; exit 1; }
    [[ ! -e "$drop" ]] || cmp -s "$drop" "$dst/prestorage.conf" || { echo 'Drop-in changed; refusing deletion'; exit 1; }
    rm -f "$unit" "$drop"
    systemctl daemon-reload
    # Keep installed files and logs for review; no running storage action.
    echo 'Boot integration removed. Inert files retained in /usr/local/lib/dx213-v2.'
    ;;
*) echo 'Usage: install.sh stage --isolated-test | arm --isolated-test | disarm | uninstall'; exit 2;;
esac
