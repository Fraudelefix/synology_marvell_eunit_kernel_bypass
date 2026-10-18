#!/bin/bash
# Experimental DSM 90080 runner. No controller unbind/reset; no volume commands.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
pkg=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode=${1:-inspect}
case "$mode" in inspect|probe|boot|scheduled) ;; *) echo 'Usage: run.sh inspect | probe --isolated-test | boot | scheduled --isolated-test'; exit 2;; esac
[[ $(id -u) = 0 ]] || { echo 'Root required'; exit 1; }
if [[ ( "$mode" = probe || "$mode" = scheduled ) && ${2:-} != --isolated-test ]]; then
    echo "$mode requires --isolated-test"; exit 1
fi
cd "$pkg"
sha256sum -c SHA256SUMS >/dev/null
[[ $(cat /proc/sys/kernel/syno_hw_version) = DS920+ ]] || exit 1
[[ $(uname -r) = 4.4.302+ ]] || exit 1
[[ $(uname -v) = '#90080 SMP Wed Jul 22 00:08:29 CST 2026' ]] || exit 1
[[ $(cat /proc/sys/kernel/modules_disabled) = 0 ]] || exit 1
lock=/run/dx213-v2.lock
mkdir "$lock" || { echo 'Another invocation or stale lock exists'; exit 1; }
owned_module=0
cleanup() {
    if [[ "$owned_module" = 1 ]]; then /sbin/rmmod dx213_boot || true; fi
    rmdir "$lock" || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

snapshot() {
    local action=$1 p
    [[ ! -e /sys/module/dx213_boot ]] || { echo 'Module already loaded; refusing'; return 1; }
    /sbin/insmod "$pkg/dx213_boot.ko" action="$action" isolated_test=1
    owned_module=1
    p=/sys/module/dx213_boot/parameters
    state=$(cat "$p/state")
    mask=$(cat "$p/disk_mask")
    echo "state=$state disk_mask=$mask flags=$(cat "$p/flags_snapshot") sstatus=$(cat "$p/sstatus_snapshot") unique=$(cat "$p/pmp_unique") class=$(cat "$p/device_class")"
    echo "raw_ports=$(cat "$p/raw_ports") pmp_links=$(cat "$p/pmp_links_snapshot") vendor=$(cat "$p/pmp_vendor") device=$(cat "$p/pmp_device") emid=$(cat "$p/pmp_emid") refusal_detail=$(cat "$p/refusal_detail")"
    /sbin/rmmod dx213_boot
    owned_module=0
}

if [[ "$mode" = inspect ]]; then
    snapshot 0
    echo 'Snapshot only. 1=absent 2=eligible 4=ready 5=busy 6=refused.'
    exit 0
fi

if [[ "$mode" = scheduled ]]; then
    [[ "$pkg" = /usr/local/lib/dx213-scheduler ]] || {
        echo 'Scheduled mode requires its separate root-owned installation'; exit 1;
    }
    [[ ! -e /usr/local/lib/dx213-v2/boot.enabled ]] || {
        echo 'REFUSED: pre-storage integration is still armed'; exit 1;
    }
    active=$(systemctl show dx213-prestorage.service -p ActiveState) || exit 1
    case "$active" in ActiveState=inactive|ActiveState=failed) ;; *)
        echo "REFUSED: pre-storage service $active"; exit 1;; esac
fi

if [[ "$mode" = boot ]]; then
    [[ "$pkg" = /usr/local/lib/dx213-v2 && -f "$pkg/boot.enabled" ]] || {
        echo 'Boot activation not armed in the installed path'; exit 1;
    }
    # Root fs, not /volume1. Never try to stop storage to make these checks pass.
    if awk '$2 ~ /^\/volume[0-9]+$/ {found=1} END {exit !found}' /proc/mounts; then
        echo 'Refusing late invocation: a data volume is mounted'; exit 1
    fi
    if grep -Eq '^md([2-9]|[1-9][0-9]+)[[:space:]]*:' /proc/mdstat; then
        echo 'Refusing late invocation: a data MD array already exists'; exit 1
    fi
    for svc in syno-space.service syno-vspace.service syno-volume.service; do
        active=$(systemctl show "$svc" -p ActiveState)
        [[ "$active" = ActiveState=inactive ]] || {
            echo "Refusing: $svc $active"; exit 1;
        }
    done
fi

# Do not probe a host exposing an existing block device, even if unmounted.
hostpath=/sys/devices/pci0000:00/0000:00:13.0/0000:01:00.0/ata6/host5
[[ -d "$hostpath" ]] || { echo 'Expected eSATA host topology absent'; exit 1; }
if [[ -n $(find "$hostpath" -type d -name block -print -quit) ]]; then
    if [[ "$mode" = scheduled ]]; then
        snapshot 0
        if [[ "$state" = 4 && "$mask" != 0 ]]; then
            echo 'ALREADY_READY: DX213 disk detected; no reprobe performed. Volume mounting is not verified.'
            exit 0
        fi
    fi
    echo 'Target already exposes block devices: no reprobe permitted'; exit 1
fi

# Bounded retries for initial driver activity; no change on refused snapshots.
deadline=$((SECONDS+30))
while :; do
    snapshot 0
    case "$state" in
        1) echo 'No connected PHY: no changes made'; exit 0;;
        2) break;;
        5) (( SECONDS < deadline )) || { echo 'Initial driver activity did not settle'; exit 1; }; sleep 1;;
        *) echo 'Target is not eligible for a connected reprobe'; exit 1;;
    esac
done

if [[ "$mode" = scheduled ]]; then
    # Atomic, root-owned /run marker: at most one mutation attempt per boot.
    # Never remove it on failure: a queued EH request can outlive this process.
    mkdir /run/dx213-scheduler-attempt || {
        echo 'REFUSED: scheduled reprobe already attempted this boot'; exit 1;
    }
fi
snapshot 1
[[ "$state" = 3 ]] || { echo 'No reprobe queued'; exit 1; }
deadline=$((SECONDS+180))
while (( SECONDS < deadline )); do
    sleep 2
    snapshot 0
    if [[ "$state" = 4 && "$mask" != 0 ]]; then
        # Allow udev to finish device-node creation. Does not trigger a new scan.
        udevadm settle --timeout=20 || { echo 'udev did not settle'; exit 1; }
        [[ -n $(find "$hostpath" -type d -name block -print -quit) ]] || {
            echo 'Driver ready but block-device publication not observed'; exit 1;
        }
        echo 'READY: DX213 data disk detected. Existing DSM assembly may proceed.'
        if [[ "$mode" = scheduled ]]; then
            echo 'DETECTION_ONLY: no assembly or mount requested; verify the existing pool in DSM.'
        fi
        if [[ "$mode" = probe ]]; then
            cat /proc/sys/kernel/random/boot_id > "$pkg/connected-probe.ok"
        fi
        exit 0
    fi
done
echo 'FAILED: readiness deadline expired. Flag may remain changed and libata work may still be active.'
echo 'No rollback, forced detach, repair or controller reset has been attempted.'
exit 1
