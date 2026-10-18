#!/usr/bin/env python3
"""Shell control-flow tests in a temporary fake NAS. Never load a module.
The production script is copied with absolute paths rooted inside a temporary
folder and external commands replaced by local fakes. Not a DSM boot simulation.
"""
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
CASES = 0

def case(mode, scenario, expected):
    global CASES
    with tempfile.TemporaryDirectory(prefix='dx213-runner-') as td:
        root = Path(td)
        pkg = root / ('usr/local/lib/dx213-scheduler' if mode == 'scheduled' else 'usr/local/lib/dx213-v2')
        pkg.mkdir(parents=True)
        bindir = root / 'bin'; bindir.mkdir()
        def put(path, text):
            p = root / path.lstrip('/'); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text); return p
        for name, content in {
            '/proc/sys/kernel/syno_hw_version': 'DS920+\n',
            '/proc/sys/kernel/modules_disabled': '0\n',
            '/proc/sys/kernel/random/boot_id': 'test-boot-id\n',
            '/proc/mounts': '/dev/md0 / ext4 rw 0 0\n',
            '/proc/mdstat': 'md0 : active raid1 sata1p1[0]\n',
        }.items(): put(name, content)
        (root/'run').mkdir()
        host = root/'sys/devices/pci0000:00/0000:00:13.0/0000:01:00.0/ata6/host5'
        host.mkdir(parents=True)
        script = (SOURCE/'run.sh').read_text()
        # Each production absolute prefix is replaced exactly once by Python.
        import re
        script = re.sub(r'(?<![A-Za-z0-9_/])/(?:usr/local/lib|proc|sys|run|sbin)(?=/)', lambda m: td+m[0], script)
        script = script.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', f'PATH={bindir}:/usr/bin:/bin')
        (pkg/'run.sh').write_text(script)
        if mode != 'scheduled': (pkg/'boot.enabled').touch()
        def command(name, text):
            p = bindir/name; p.write_text('#!/bin/bash\n'+text); p.chmod(0o700)
        command('id', 'echo 0\n')
        command('sha256sum', 'exit 0\n') # checksum verification tested separately
        command('uname', '''if [[ "$1" = -r ]]; then echo '4.4.302+'; else echo '#90080 SMP Wed Jul 22 00:08:29 CST 2026'; fi\n''')
        command('udevadm', 'exit 0\n')
        command('systemctl', "echo ActiveState=inactive\n")
        command('sleep', 'exit 0\n')
        insmod = put('/sbin/insmod', '''#!/bin/bash
set -eu
p="$FAKE_ROOT/sys/module/dx213_boot/parameters"
mkdir -p "$p"
action=${2#action=}
echo "$action" >> "$FAKE_ROOT/actions"
if [[ "$action" = 1 ]]; then
    state=3
    touch "$FAKE_ROOT/applied"
elif [[ -f "$FAKE_ROOT/applied" ]]; then
    state=4
    mkdir -p "$FAKE_ROOT/sys/devices/pci0000:00/0000:00:13.0/0000:01:00.0/ata6/host5/target5:0:0/5:0:0:0/block/sata2"
else
    state=${FAKE_STATE:-2}
fi
echo "$state" > "$p/state"
echo 1 > "$p/disk_mask"
for k in flags_snapshot sstatus_snapshot pmp_unique device_class raw_ports pmp_links_snapshot pmp_vendor pmp_device pmp_emid refusal_detail; do echo 0 > "$p/$k"; done
'''); insmod.chmod(0o700)
        rmmod = put('/sbin/rmmod', '#!/bin/bash\nrm -rf "$FAKE_ROOT/sys/module/dx213_boot"\n'); rmmod.chmod(0o700)
        env = dict(os.environ, FAKE_ROOT=td)
        if scenario == 'absent': env['FAKE_STATE']='1'
        if scenario == 'refused': env['FAKE_STATE']='6'
        if scenario == 'existing-block': (host/'block').mkdir()
        if scenario == 'mounted': put('/proc/mounts', '/dev/x /volume1 btrfs rw 0 0\n')
        if scenario == 'assembled': put('/proc/mdstat', 'md3 : active raid1 sata2p5[0]\n')
        if scenario == 'active-service': command('systemctl', 'echo ActiveState=active\n')
        if scenario == 'disarmed': (pkg/'boot.enabled').unlink()
        if scenario == 'wrong-build': command('uname', 'echo different\n')
        if scenario == 'bad-checksum': command('sha256sum', 'exit 1\n')
        if scenario == 'already-ready':
            (host/'block').mkdir()
            env['FAKE_STATE']='4'
        if scenario == 'armed-prestorage': put('/usr/local/lib/dx213-v2/boot.enabled', '')
        if scenario == 'service-query-failed': command('systemctl', 'exit 1\n')
        if scenario == 'previous-attempt': (root/'run/dx213-scheduler-attempt').mkdir()
        if scenario == 'apply-failed':
            insmod.write_text(insmod.read_text().replace('state=3', 'exit 1'))
        args = ['bash', str(pkg/'run.sh'), mode]
        if mode in ('probe', 'scheduled') and scenario != 'no-auth': args += ['--isolated-test']
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == expected, (mode,scenario,result.stdout,result.stderr)
        actions = (root/'actions').read_text().splitlines() if (root/'actions').exists() else []
        successful_probe = expected and mode in ('probe','boot','scheduled') and scenario in ('normal','mounted','assembled')
        attempted = successful_probe or scenario == 'apply-failed'
        assert actions.count('1') == int(attempted), (mode,scenario,actions)
        assert not (root/'run/dx213-v2.lock').exists()
        if scenario != 'apply-failed': assert not (root/'sys/module/dx213_boot').exists()
        assert (pkg/'connected-probe.ok').exists() == (successful_probe and mode=='probe')
        if mode == 'scheduled':
            assert (root/'run/dx213-scheduler-attempt').exists() == (attempted or scenario == 'previous-attempt')
        CASES += 1

for args in [
    ('inspect','normal',True),('probe','normal',True),('boot','normal',True),
    ('probe','absent',True),('boot','absent',True),('probe','refused',False),
    ('probe','existing-block',False),('boot','mounted',False),
    ('boot','assembled',False),('boot','active-service',False),
    ('boot','disarmed',False),('probe','wrong-build',False),
    ('probe','bad-checksum',False),('probe','no-auth',False),
    ('scheduled','normal',True),('scheduled','mounted',True),
    ('scheduled','assembled',True),('scheduled','already-ready',True),
    ('scheduled','existing-block',False),('scheduled','absent',True),
    ('scheduled','refused',False),('scheduled','armed-prestorage',False),
    ('scheduled','active-service',False),('scheduled','service-query-failed',False),
    ('scheduled','previous-attempt',False),('scheduled','apply-failed',False),
    ('scheduled','wrong-build',False),('scheduled','bad-checksum',False),
    ('scheduled','no-auth',False),
]: case(*args)
print(f'PASS: {CASES} runner cases in temporary fake filesystem; no kernel calls')
