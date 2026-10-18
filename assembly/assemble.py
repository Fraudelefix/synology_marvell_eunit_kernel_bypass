#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact DSM 90080, one-disk DX213 pool only. No raw MD/LVM/mount mutations."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

PKG = Path('/usr/local/lib/dx213-assembly')
CONFIG = PKG / 'target.json'
HOST = Path('/sys/devices/pci0000:00/0000:00:13.0/0000:01:00.0/ata6/host5')
WEBAPI = '/usr/syno/bin/synowebapi'
LOCK = Path('/run/dx213-v2.lock')
ATTEMPT = Path('/run/dx213-assembly-attempt')
ENV = dict(os.environ, PATH='/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C')

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def one(items, message):
    require(len(items) == 1, message)
    return items[0]

def decode(text):
    # synowebapi may print a diagnostic line containing param={} before JSON.
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.lstrip().startswith('{')]
    require(bool(starts), 'No standalone JSON response')
    result = json.loads('\n'.join(lines[starts[0]:]))
    require(isinstance(result, dict) and result.get('success') is True,
            'DSM API did not report success')
    return result

def api(method, pool_uuid=None):
    args = [WEBAPI, '--exec', 'api=SYNO.Storage.CGI.' + ('Pool' if pool_uuid else 'Storage'),
            'method=' + method, 'version=1']
    if pool_uuid:
        args += ['space_uuid=' + json.dumps(pool_uuid), 'force=false']
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=45, env=ENV)
    require(result.returncode == 0, 'synowebapi failed; no automatic retry of a mutation')
    return decode(result.stdout)

def load_info():
    data = api('load_info').get('data')
    require(isinstance(data, dict), 'Missing storage inventory')
    return data

def pool_in(data, uuid):
    return one([p for key in ('storagePools', 'missing_pools', 'detected_pools')
                for p in data.get(key, []) if p.get('uuid') == uuid],
               'Expected pool absent or duplicated')

def disk_for(data, pool):
    ids = pool.get('disks')
    require(isinstance(ids, list) and len(ids) == 1, 'Only a single-disk pool is supported')
    disk = one([d for d in data.get('disks', []) if d.get('id') == ids[0]], 'Disk missing or duplicated')
    container = disk.get('container', {})
    require(container.get('type') == 'ebox' and container.get('str') == 'DX213-1', 'Disk is not in DX213-1')
    require(disk.get('slot_id') == 1 and disk.get('has_system') is False, 'Only non-system DX213 bay 1 supported')
    require(disk.get('status') in ('normal', 'data_detected'), 'Disk status not admissible')
    require(disk.get('action_status', {}).get('action_name') == 'idle'
            and disk.get('is_erasing') is False and disk.get('smart_testing') is False,
            'Disk operation in progress or unknown')
    require(disk.get('used_by') == pool.get('id'), 'Disk/pool assignment mismatch')
    return disk

def classify(data, cfg):
    env = data.get('env', {})
    system = env.get('status', {})
    require(env.get('model_name') == 'DS920+', 'Wrong inventory model')
    require(all(system.get(k) is False for k in ('system_crashed', 'system_need_repair', 'system_rebuilding')),
            'Internal system not healthy or state unknown')
    p = pool_in(data, cfg['pool_uuid'])
    d = disk_for(data, p)
    require(d.get('serial') == cfg['serial'] and d.get('model') == cfg['model'], 'Disk identity changed')
    require(p.get('id') == cfg['pool_id'] and p.get('device_type') == 'shr_without_disk_protect', 'Pool identity/type changed')
    require(p.get('disk_failure_number') == 0 and p.get('missing_drives') == [], 'Missing or failed pool members')
    require(p.get('cache_disks') == [], 'Cached pools unsupported')
    raids = p.get('raids', [])
    raid = one(raids, 'Exactly one RAID component required')
    require(raid.get('raidPath') == cfg['raid'] and raid.get('designedDiskCount') == 1, 'RAID identity changed')
    member = one(raid.get('devices', []), 'Exactly one RAID member required')
    require(member.get('id') == d['id'], 'RAID member mismatch')
    if p.get('status') == 'assembling' or p.get('is_actioning') is True:
        return 'busy', d
    require(env.get('fs_acting') is False and env.get('is_space_actioning') is False,
            'Other storage operation active or unknown')
    if p.get('status') == 'normal':
        require(p.get('is_writable') is True, 'Pool is not writable')
        v = one([v for v in data.get('volumes', []) if v.get('uuid') == cfg['volume_uuid']], 'Expected volume absent')
        require(v.get('pool_path') == p['id'] and v.get('vol_path') == cfg['mount']
                and v.get('status') == 'normal' and v.get('is_writable') is True
                and v.get('is_encrypted') is False, 'Volume not normal/writable or identity changed')
        return 'ready', d
    require(p.get('status') == 'missing' and p.get('can_assemble') is True
            and p.get('is_unassembled_pool') is True and p.get('repair_action') == 'reassemble'
            and p.get('volumes') == [cfg['mount']], 'DSM does not authorize ordinary reassembly')
    return 'eligible', d

def topology(disk):
    name = disk['id']
    require(re.fullmatch(r'sata[0-9]+', name) is not None, 'Unexpected disk name')
    resolved = (Path('/sys/class/block') / name).resolve(strict=True)
    require(str(resolved).startswith(str(HOST) + '/'), 'Disk is not on the expected eSATA host')
    require(disk.get('device') == '/dev/' + name, 'Device path mismatch')

def mount_entry(path):
    rows = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    matches = [r for r in rows if r[4] == path]
    require(len(matches) <= 1, 'Stacked mount unsupported')
    return matches[0] if matches else None

def mounted(cfg, disk):
    row = mount_entry(cfg['mount'])
    if not row:
        return False
    require('rw' in row[5].split(','), 'Expected mount is read-only')
    # Btrfs mountinfo can report an anonymous 0:N device; resolve the block
    # source instead, then prove its ancestry through the enrolled MD.
    sep = row.index('-')
    require(row[sep + 1] in ('btrfs', 'ext4') and 'rw' in row[sep + 3].split(','),
            'Unsupported or read-only filesystem')
    source = row[sep + 2]
    require(source.startswith('/dev/') and '\\' not in source, 'Unexpected mount source')
    dev = os.stat(source)
    require(stat.S_ISBLK(dev.st_mode), 'Mount source is not a block device')
    start = Path('/sys/dev/block') / ('%d:%d' % (os.major(dev.st_rdev), os.minor(dev.st_rdev)))
    nodes, leaves = set(), set()
    def walk(node):
        node = node.resolve(strict=True)
        require(node.name not in nodes, 'Cycle or shared device graph unsupported')
        nodes.add(node.name)
        children = list((node/'slaves').iterdir()) if (node/'slaves').is_dir() else []
        if children:
            for child in children: walk(child)
        else:
            leaves.add(node.name)
            require(str(node).startswith(str(HOST) + '/'), 'Mount includes a device outside eSATA')
    walk(start)
    require(Path(cfg['raid']).name in nodes and leaves == {disk['id'] + 'p5'}, 'Mounted device mapping differs from enrolled pool')
    return True

def trusted(path):
    st = path.lstat()
    require(not stat.S_ISLNK(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022,
            'Untrusted permissions: ' + str(path))

def guard():
    require(os.geteuid() == 0, 'Root required')
    require(Path(__file__).resolve().parent == PKG, 'Use the separately installed copy')
    for p in (PKG, PKG/'assemble.py', PKG/'SHA256SUMS'): trusted(p)
    subprocess.run(['/usr/bin/sha256sum' if Path('/usr/bin/sha256sum').exists() else '/bin/sha256sum',
                    '-c', 'SHA256SUMS'], cwd=str(PKG), check=True, stdout=subprocess.DEVNULL)
    require(Path('/proc/sys/kernel/syno_hw_version').read_text().strip() == 'DS920+', 'Wrong NAS')
    u = os.uname()
    require(u.release == '4.4.302+' and u.version == '#90080 SMP Wed Jul 22 00:08:29 CST 2026', 'Wrong kernel')
    require(not Path('/usr/local/lib/dx213-v2/boot.enabled').exists(), 'Pre-storage service is armed')

def enroll(uuid):
    require(not CONFIG.exists(), 'Target already enrolled; refusing overwrite')
    require(re.fullmatch(r'[A-Za-z0-9-]{20,80}', uuid) is not None, 'Invalid pool UUID')
    data = load_info()
    p = pool_in(data, uuid)
    d = disk_for(data, p)
    v = one([v for v in data.get('volumes', []) if v.get('pool_path') == p.get('id')], 'Exactly one mounted volume required')
    cfg = dict(pool_uuid=uuid, pool_id=p['id'], serial=d['serial'], model=d['model'],
               raid=one(p['raids'], 'One RAID required')['raidPath'], volume_uuid=v['uuid'], mount=v['vol_path'])
    require(re.fullmatch(r'/volume[1-9][0-9]*', cfg['mount']) is not None
            and re.fullmatch(r'/dev/md[2-9][0-9]*', cfg['raid']) is not None, 'Unexpected volume/RAID path')
    state, disk = classify(data, cfg)
    topology(disk)
    require(state == 'ready' and mounted(cfg, disk), 'Enroll only a healthy, mounted DX213 pool')
    fd = os.open(str(CONFIG), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(cfg, f, indent=2)
        f.write('\n')
    print('ENROLLED: healthy DX213 pool identity saved locally; no assembly requested')

def run(mode):
    trusted(CONFIG)
    cfg = json.loads(CONFIG.read_text())
    data = load_info()
    state, disk = classify(data, cfg)
    topology(disk)
    is_mounted = mounted(cfg, disk)
    print('ASSEMBLY_INSPECT: state={} mounted={}'.format(state, is_mounted), flush=True)
    if mode == 'inspect':
        return
    if state == 'ready' and is_mounted:
        print('MOUNT_READY: already mounted; no assembly requested')
        return
    require(not is_mounted, 'Refusing action on a mounted but inconsistent pool')
    if state == 'eligible':
        require(not Path('/sys/class/block', Path(cfg['raid']).name).exists(), 'RAID already exists; refusing reassembly')
        # Persistent for this boot even on timeout: backend work may continue.
        ATTEMPT.mkdir(mode=0o700)
        print('ASSEMBLY_REQUEST: exact enrolled pool; force=false', flush=True)
        api('reassemble', cfg['pool_uuid'])
    else:
        require(state in ('busy', 'ready'), 'Unexpected assembly state')
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        time.sleep(3)
        state, disk = classify(load_info(), cfg)
        topology(disk)
        if state == 'ready' and mounted(cfg, disk):
            print('MOUNT_READY: enrolled DX213 volume is mounted read-write')
            return
    raise RuntimeError('Mount not confirmed before deadline; no retry or rollback performed')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('enroll', 'inspect', 'assemble'))
    parser.add_argument('--pool-uuid')
    parser.add_argument('--isolated-test', action='store_true')
    args = parser.parse_args()
    require(args.mode == 'inspect' or args.isolated_test, '--isolated-test required')
    guard()
    LOCK.mkdir(mode=0o700)
    try:
        if args.mode == 'enroll':
            require(bool(args.pool_uuid), '--pool-uuid required')
            enroll(args.pool_uuid)
        else:
            run(args.mode)
    finally:
        LOCK.rmdir()

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ASSEMBLY_STOP: ' + str(exc), file=sys.stderr)
        sys.exit(1)
