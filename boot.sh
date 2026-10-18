#!/bin/bash
set -u
exec >> /var/log/dx213-v2.log 2>&1
date -u
echo 'Beginning experimental pre-storage DX213 detection'
/usr/local/lib/dx213-v2/run.sh boot
rc=$?
echo "DX213 pre-storage result=$rc"
exit "$rc"
