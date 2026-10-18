#!/usr/bin/env python3
"""Regenerate the release file manifest after reviewing changes; no NAS writes."""
from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
skip_dirs={'.git','__pycache__','.tmp_versions'}
skip_files={'connected-probe.ok','boot.enabled','.dx213-v2-owned','Module.symvers','modules.order','target.json'}
assembly=root/'assembly'
if assembly.is_dir():
    names=('assemble.py','task.sh')
    (assembly/'SHA256SUMS').write_text(''.join(hashlib.sha256((assembly/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
files=[]
for p in root.rglob('*'):
    rel=p.relative_to(root)
    if p == root/'SHA256SUMS': continue
    if not p.is_file() or any(part in skip_dirs for part in rel.parts): continue
    if p.name in skip_files or p.name.endswith(('.o','.mod.c','.pyc','.log')) or p.name.endswith('.cmd'): continue
    if p.is_symlink(): raise SystemExit(f'Refusing symlink: {rel}')
    files.append(p)
(root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in sorted(files)))
print(f'SHA256SUMS: {len(files)} files. Review before distributing.')
