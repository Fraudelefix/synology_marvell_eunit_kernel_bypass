#!/bin/bash
# Read-only commands. Does not load a module or change driver state.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
date -u
uname -a
cat /etc.defaults/VERSION
cat /proc/sys/kernel/syno_hw_version
cat /proc/mdstat
cat /proc/mounts
systemctl show dx213-prestorage.service syno-space.service syno-vspace.service syno-volume.service -p ActiveState -p SubState -p After -p Before -p ExecMainStatus
cat /var/log/dx213-v2.log 2>/dev/null || true
cat /var/log/dx213-scheduler.log 2>/dev/null || true
dmesg
