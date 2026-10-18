#!/usr/bin/env python3
"""Installer isolation tests. All destinations and kernel facts are fake."""
from pathlib import Path
import hashlib, os, re, subprocess, tempfile

source = Path(__file__).resolve().parents[1]
cases = 0
for scenario in ('normal', 'no-auth', 'wrong-build', 'bad-checksum', 'non-root-fs', 'existing'):
    with tempfile.TemporaryDirectory(prefix='dx213-scheduler-stage-') as td:
        root = Path(td)
        pkg = root/'package'; pkg.mkdir()
        bindir = root/'bin'; bindir.mkdir()
        (root/'usr/local/lib').mkdir(parents=True)
        model = root/'proc/sys/kernel/syno_hw_version'
        model.parent.mkdir(parents=True); model.write_text('DS920+\n')
        script = (source/'install-scheduler.sh').read_text()
        script = re.sub(r'(?<![A-Za-z0-9_/])/(?:usr/local/lib|proc)(?=/|[\s\]])', lambda m: td+m[0], script)
        script = script.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', f'PATH={bindir}:/usr/bin:/bin')
        (pkg/'install-scheduler.sh').write_text(script)
        (pkg/'scheduler.sh').write_text('reviewed content\n')
        # Deliberately unlisted runtime files must not reach the destination.
        (pkg/'boot.enabled').touch()
        (pkg/'connected-probe.ok').write_text('private proof\n')
        (pkg/'SHA256SUMS').write_text(''.join(
            hashlib.sha256((pkg/n).read_bytes()).hexdigest()+'  '+n+'\n'
            for n in ('install-scheduler.sh', 'scheduler.sh')))
        if scenario == 'bad-checksum': (pkg/'scheduler.sh').write_text('tampered\n')
        commands = {
            'id': 'echo 0', 'chown': 'exit 0',
            'uname': "if [[ $1 = -r ]]; then echo 4.4.302+; else echo '#90080 SMP Wed Jul 22 00:08:29 CST 2026'; fi",
            'df': "echo '/dev/md0 100 10 90 10% /'",
            'systemctl': 'echo FORBIDDEN; exit 99',
        }
        if scenario == 'wrong-build': commands['uname']='echo unsupported'
        if scenario == 'non-root-fs': commands['df']="echo '/dev/x 100 10 90 10% /volume1'"
        for name, body in commands.items():
            p = bindir/name; p.write_text('#!/bin/bash\n'+body+'\n'); p.chmod(0o700)
        dst = root/'usr/local/lib/dx213-scheduler'
        if scenario == 'existing': dst.mkdir(); (dst/'sentinel').touch()
        args = ['bash', str(pkg/'install-scheduler.sh'), 'stage']
        if scenario != 'no-auth': args.append('--isolated-test')
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        assert (result.returncode == 0) == (scenario == 'normal'), (scenario, result.stdout, result.stderr)
        assert 'FORBIDDEN' not in result.stdout
        if scenario == 'normal':
            assert sorted(p.name for p in dst.iterdir()) == ['SHA256SUMS','install-scheduler.sh','scheduler.sh']
            assert (dst.stat().st_mode & 0o777) == 0o700
            assert (dst/'scheduler.sh').read_text() == 'reviewed content\n'
        elif scenario == 'existing': assert (dst/'sentinel').exists()
        else: assert not dst.exists()
        cases += 1
print(f'PASS: {cases} scheduler staging cases; real checksums; fake NAS filesystem')
