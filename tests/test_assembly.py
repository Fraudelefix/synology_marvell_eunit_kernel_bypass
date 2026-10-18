#!/usr/bin/env python3
"""Sanitized observed DSM inventories; no real API calls or storage changes."""
import copy
import importlib.util
import json
import os
import stat
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assemble', ROOT/'assembly/assemble.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
READY = json.loads((ROOT/'tests/fixtures/assembly-ready.json').read_text())
MISSING = json.loads((ROOT/'tests/fixtures/assembly-missing.json').read_text())
CFG = dict(pool_uuid='TESTPOOL-0000-0000-0000-000000000000', pool_id='reuse_2',
           serial='TEST-DX213-DISK', model='WD30EZRX-00MMMB0', raid='/dev/md3',
           volume_uuid='TESTVOLUME-0000-0000-000000000000', mount='/volume2')

class AssemblyTests(unittest.TestCase):
    def test_observed_ready(self): self.assertEqual(a.classify(READY,CFG)[0], 'ready')
    def test_observed_missing(self): self.assertEqual(a.classify(MISSING,CFG)[0], 'eligible')
    def test_busy_no_mutation_class(self):
        d=copy.deepcopy(READY); d['storagePools'][0]['is_actioning']=True
        self.assertEqual(a.classify(d,CFG)[0], 'busy')
    def test_refusals(self):
        mutations = [
            lambda d: d['disks'][0].update(serial='DIFFERENT'),
            lambda d: d['disks'][0].update(has_system=True),
            lambda d: d['disks'][0]['container'].update(type='internal'),
            lambda d: d['disks'][0].update(slot_id=2),
            lambda d: d['disks'][0].update(status='crashed'),
            lambda d: d['disks'][0].update(is_erasing=True),
            lambda d: d['disks'][0].update(used_by='reuse_1'),
            lambda d: d['missing_pools'][0].update(can_assemble=False),
            lambda d: d['missing_pools'][0].update(missing_drives=['sata3']),
            lambda d: d['missing_pools'][0].update(disk_failure_number=1),
            lambda d: d['missing_pools'][0].update(disks=['sata2','sata3']),
            lambda d: d['missing_pools'][0].update(cache_disks=['nvme0']),
            lambda d: d['missing_pools'][0].update(repair_action='repair'),
            lambda d: d['missing_pools'][0].update(volumes=['/volume1']),
            lambda d: d['missing_pools'][0]['raids'][0].update(raidPath='/dev/md2'),
            lambda d: d['env']['status'].update(system_crashed=True),
            lambda d: d['env'].update(is_space_actioning=True),
            lambda d: d['missing_pools'].append(copy.deepcopy(d['missing_pools'][0])),
        ]
        for i, mutation in enumerate(mutations):
            with self.subTest(guard=i):
                d=copy.deepcopy(MISSING); mutation(d)
                with self.assertRaises(RuntimeError): a.classify(d,CFG)
    def test_parser_ignores_prefix_braces(self):
        self.assertEqual(a.decode('[Line 295] param={}\n{\n"success":true\n}')['success'],True)
    def test_parser_rejects_failure(self):
        with self.assertRaises(RuntimeError): a.decode('{\n"success":false\n}')
    def test_compact_json(self):
        self.assertTrue(a.decode('{"success":true}')['success'])
    def test_mount_graph(self):
        cfg=copy.deepcopy(CFG)
        disk=READY['disks'][0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            host=root/'host5'; leaf=host/'target/block/sata2/sata2p5';leaf.mkdir(parents=True)
            md=root/'md3';(md/'slaves').mkdir(parents=True)
            (md/'slaves/sata2p5').symlink_to(leaf)
            dm=root/'dm0';(dm/'slaves').mkdir(parents=True)
            (dm/'slaves/md3').symlink_to(md)
            real_path=a.Path
            def path(value):
                return root if value=='/sys/dev/block' else real_path(value)
            (root/'253:0').symlink_to(dm)
            row=['1','0','0:40','/','/volume2','rw','-','btrfs','/dev/mapper/cachedev_0','rw']
            real_stat=os.stat
            def source_stat(value, *args, **kwargs):
                if str(value)=='/dev/mapper/cachedev_0':
                    return SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(253,0))
                return real_stat(value,*args,**kwargs)
            with patch.object(a,'HOST',host),patch.object(a,'Path',side_effect=path),patch.object(a,'mount_entry',return_value=row),patch.object(a.os,'stat',side_effect=source_stat):
                self.assertTrue(a.mounted(cfg,disk))
                row[5]='ro'
                with self.assertRaises(RuntimeError): a.mounted(cfg,disk)
                row[5]='rw'
                (md/'slaves/sata2p5').unlink()
                wrong=root/'internal/sata1p5';wrong.mkdir(parents=True)
                (md/'slaves/sata1p5').symlink_to(wrong)
                with self.assertRaises(RuntimeError): a.mounted(cfg,disk)
    def test_parser_rejects_trailing_junk(self):
        with self.assertRaises(ValueError): a.decode('{\n"success":true\n}\njunk')
    def test_api_arguments(self):
        with patch.object(a.subprocess,'run') as run:
            run.return_value.returncode=0
            run.return_value.stdout='{\n"success":true\n}'
            a.api('reassemble', CFG['pool_uuid'])
            args=run.call_args[0][0]
            self.assertIn('force=false',args)
            self.assertIn('space_uuid='+json.dumps(CFG['pool_uuid']),args)
            self.assertNotIn('runner=root',args)
            self.assertEqual(run.call_args[1]['timeout'],45)
    def test_run_modes(self):
        for mode, before, mount, expected in [('inspect',MISSING,False,0),('assemble',READY,True,0),('assemble',MISSING,False,1)]:
            with self.subTest(mode=mode,mounted=mount), tempfile.TemporaryDirectory() as td:
                cfg=Path(td)/'target.json';cfg.write_text(json.dumps(CFG))
                marker=Path(td)/'attempt'
                with patch.object(a,'CONFIG',cfg),patch.object(a,'ATTEMPT',marker),patch.object(a,'trusted'),patch.object(a,'topology'),patch.object(a,'load_info',side_effect=[before,READY]),patch.object(a,'mounted',side_effect=[mount,True]),patch.object(a,'api') as api,patch.object(a.time,'sleep'),patch.object(a.Path,'exists',return_value=False):
                    a.run(mode)
                    self.assertEqual(api.call_count,expected)
                self.assertEqual(marker.exists(),bool(expected))
    def test_failed_mutation_keeps_marker(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'target.json';cfg.write_text(json.dumps(CFG))
            marker=Path(td)/'attempt'
            with patch.object(a,'CONFIG',cfg),patch.object(a,'ATTEMPT',marker),patch.object(a,'trusted'),patch.object(a,'topology'),patch.object(a,'load_info',return_value=MISSING),patch.object(a,'mounted',return_value=False),patch.object(a,'api',side_effect=RuntimeError('failed')),patch.object(a.Path,'exists',return_value=False):
                with self.assertRaises(RuntimeError): a.run('assemble')
            self.assertTrue(marker.exists())
    def test_existing_marker_refuses(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'target.json';cfg.write_text(json.dumps(CFG))
            marker=Path(td)/'attempt';marker.mkdir()
            with patch.object(a,'CONFIG',cfg),patch.object(a,'ATTEMPT',marker),patch.object(a,'trusted'),patch.object(a,'topology'),patch.object(a,'load_info',return_value=MISSING),patch.object(a,'mounted',return_value=False),patch.object(a,'api') as api,patch.object(a.Path,'exists',return_value=False):
                with self.assertRaises(FileExistsError): a.run('assemble')
                api.assert_not_called()
    def test_enroll_mounted_identity_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'target.json'
            with patch.object(a,'CONFIG',cfg),patch.object(a,'load_info',return_value=READY),patch.object(a,'topology'),patch.object(a,'mounted',return_value=True):
                a.enroll(CFG['pool_uuid'])
                self.assertEqual(json.loads(cfg.read_text()),CFG)
                self.assertEqual(cfg.stat().st_mode & 0o777,0o600)
                with self.assertRaises(RuntimeError): a.enroll(CFG['pool_uuid'])
    def test_enroll_refuses_unmounted(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'target.json'
            with patch.object(a,'CONFIG',cfg),patch.object(a,'load_info',return_value=READY),patch.object(a,'topology'),patch.object(a,'mounted',return_value=False):
                with self.assertRaises(RuntimeError): a.enroll(CFG['pool_uuid'])
                self.assertFalse(cfg.exists())

if __name__=='__main__': unittest.main()
