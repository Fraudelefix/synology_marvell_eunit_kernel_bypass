#!/bin/bash
# GPL-2.0-only. Task Scheduler entry point; detection only, not pool assembly.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
[[ $(id -u) = 0 ]] || { echo 'Root required'; exit 1; }
[[ ${1:-} = --isolated-test ]] || { echo 'Requires --isolated-test'; exit 2; }
pkg=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[[ "$pkg" = /usr/local/lib/dx213-scheduler ]] || { echo 'Use the installed copy'; exit 1; }
exec >> /var/log/dx213-scheduler.log 2>&1
date -u
echo "Task Scheduler experiment; boot_id=$(cat /proc/sys/kernel/random/boot_id)"
rc=0
/bin/bash "$pkg/run.sh" scheduled --isolated-test || rc=$?
echo "DETECTION_RESULT=$rc (does not confirm volume mounting)"
cat /proc/mdstat
df -h
exit "$rc"
