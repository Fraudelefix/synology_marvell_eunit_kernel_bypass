#!/usr/bin/env python3
"""Exercise install lifecycle on a rooted copy, with fake DSM/systemctl."""
from pathlib import Path
import os, re, shutil, subprocess, tempfile
source=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dx213-install-') as td:
    root=Path(td); pkg=root/'package'; pkg.mkdir()
    for name in ['install.sh','run.sh','boot.sh','dx213-prestorage.service','prestorage.conf']:
        shutil.copyfile(source/name,pkg/name)
    (pkg/'SHA256SUMS').write_text('mocked for lifecycle test\n')
    (root/'usr/local/lib').mkdir(parents=True)
    (root/'etc/systemd/system').mkdir(parents=True)
    for path,value in [('proc/sys/kernel/syno_hw_version','DS920+'),('proc/sys/kernel/random/boot_id','fakeboot')]:
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value+'\n')
    bindir=root/'bin';bindir.mkdir()
    for name,body in {
        'id':'echo 0', 'uname':"echo '#90080 SMP Wed Jul 22 00:08:29 CST 2026'",
        'sha256sum':'exit 0', 'chown':'exit 0',
        'df':"echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'; echo '/dev/md0 100 10 90 10% /'",
        'systemctl':'echo "$*" >> "$FAKE_ROOT/systemctl.log"',
    }.items():
        p=bindir/name;p.write_text('#!/bin/bash\n'+body+'\n');p.chmod(0o700)
    text=(pkg/'install.sh').read_text()
    text=re.sub(r'(?<![A-Za-z0-9_/])/(?:usr/local/lib|etc/systemd/system|proc)(?=/|[\s\]])',lambda m:td+m[0],text)
    text=text.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin',f'PATH={bindir}:/usr/bin:/bin')
    (pkg/'install.sh').write_text(text)
    def run(*args,ok=True):
        r=subprocess.run(['bash',str(pkg/'install.sh'),*args],env=dict(os.environ,FAKE_ROOT=td),capture_output=True,text=True)
        assert (r.returncode==0)==ok,(args,r.stdout,r.stderr)
    dst=root/'usr/local/lib/dx213-v2'
    unit=root/'etc/systemd/system/dx213-prestorage.service'
    drop=root/'etc/systemd/system/syno-space.service.d/90-dx213-v2.conf'
    run('stage','--isolated-test',ok=False)
    assert not dst.exists()
    (pkg/'connected-probe.ok').write_text('wrongboot\n')
    run('stage','--isolated-test',ok=False)
    assert not dst.exists()
    (pkg/'connected-probe.ok').write_text('fakeboot\n')
    run('stage','--isolated-test')
    assert unit.exists() and drop.exists() and not (dst/'boot.enabled').exists()
    run('stage','--isolated-test',ok=False)
    run('arm','--isolated-test');assert (dst/'boot.enabled').exists()
    run('disarm');assert not (dst/'boot.enabled').exists()
    original=unit.read_text();unit.write_text(original+'# local change\n')
    run('uninstall',ok=False);assert unit.exists()
    unit.write_text(original)
    run('uninstall');assert not unit.exists() and not drop.exists() and dst.exists()
    assert set((root/'systemctl.log').read_text().splitlines())=={'daemon-reload'}
print('PASS: 8 installer lifecycle cases; no start/reboot; temporary filesystem only')
