#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
"""Build a file package in a NEW directory. Never opens a physical disk."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
SYSTEM_RESCUE = json.loads((HERE/'upstream.lock.json').read_text(encoding='utf-8'))['SystemRescue']
ISO_SHA256 = SYSTEM_RESCUE['sha256']
ISO_URL = SYSTEM_RESCUE['url']
ISO_NAME = 'systemrescue-' + SYSTEM_RESCUE['version'] + '.iso'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def obtain_iso(cache, url=ISO_URL, expected=ISO_SHA256):
    """Cache a verified upstream download; never expose a partial ISO as valid."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache/ISO_NAME
    if destination.exists():
        if digest(destination) != expected:
            raise ValueError('Cached ISO SHA256 mismatch: ' + str(destination) + '. Move it aside and retry, or use --iso.')
        print('Using verified cached ISO:', destination, flush=True)
        return destination
    temporary = None
    try:
        print('Downloading the pinned SystemRescue ISO from:', url, flush=True)
        request = Request(url, headers={'User-Agent': 'Hackintosh-AutoEFI-builder'})
        hasher, received, last_progress = hashlib.sha256(), 0, 0
        with urlopen(request, timeout=60) as response, tempfile.NamedTemporaryFile(
                dir=cache, prefix=ISO_NAME+'.', suffix='.part', delete=False) as stream:
            temporary = Path(stream.name)
            total = response.headers.get('Content-Length')
            total = int(total) if total is not None else None
            while chunk := response.read(1024*1024):
                stream.write(chunk)
                hasher.update(chunk)
                received += len(chunk)
                if received-last_progress >= 64*1024*1024:
                    print('Downloaded:', received//(1024*1024), 'MiB', flush=True)
                    last_progress = received
            stream.flush()
            os.fsync(stream.fileno())
        if total is not None and received != total:
            raise ValueError('Incomplete ISO download')
        if hasher.hexdigest() != expected:
            raise ValueError('Downloaded ISO SHA256 mismatch; no package was built')
        # Preserve a concurrently created cache file instead of replacing it.
        if destination.exists():
            if digest(destination) != expected:
                raise ValueError('Conflicting cached ISO appeared during download')
        else:
            temporary.replace(destination)
        print('ISO verified:', destination, flush=True)
        return destination
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, help='Use an existing official ISO instead of downloading')
    parser.add_argument('--cache-dir', type=Path, default=HERE/'cache', help='Directory for verified upstream ISO downloads')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--grub-modules', type=Path, help='Matching x86_64-efi GRUB module directory')
    args = parser.parse_args()
    seven = shutil.which('7z') or shutil.which('7zz')
    grub = shutil.which('grub-mkstandalone')
    if not seven or not grub:
        parser.error('Install 7z/7zz and grub-mkstandalone first')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output directory already exists; choose a new directory')
    try:
        iso = args.iso.resolve() if args.iso else obtain_iso(args.cache_dir)
        if digest(iso) != ISO_SHA256:
            parser.error('ISO SHA256 mismatch; expected SystemRescue 13.02 amd64')
    except (OSError, ValueError) as exc:
        parser.error(str(exc) + '\nYou can also download the pinned ISO manually and use --iso /path/to/file.iso.')
    output.mkdir(parents=True)
    package = output / 'package'
    shutil.copytree(HERE / 'package', package, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    subprocess.run([seven, 'x', '-y', '-o' + str(output/'extracted'), str(iso), 'sysresccd'], check=True)
    live = package/'HardwareCollector/live'
    (output/'extracted/sysresccd').rename(live)
    for name in ['boot/x86_64/vmlinuz', 'boot/x86_64/sysresccd.img', 'x86_64/airootfs.sfs']:
        if not (live/name).is_file():
            raise RuntimeError('Missing boot asset: ' + name)
    embedded = output/'embedded-grub.cfg'
    embedded.write_text('''insmod part_gpt
insmod part_msdos
insmod fat
insmod search_fs_file
search --no-floppy --file --set=root /HardwareCollector/identity-3eead5ee-b941-4925-b314-5ac6d8a24ad1
configfile ($root)/HardwareCollector/grub.cfg
''', encoding='utf-8')
    boot = package/'EFI/BOOT/BOOTx64.efi'
    boot.parent.mkdir(parents=True)
    command = [grub, '-O', 'x86_64-efi']
    if args.grub_modules:
        command += ['-d', str(args.grub_modules.resolve())]
    command += ['--modules=part_gpt part_msdos fat ext2 search search_fs_file search_fs_uuid probe linux chain all_video normal serial',
                '--locales=', '--fonts=', '-o', str(boot), 'boot/grub/grub.cfg='+str(embedded)]
    subprocess.run(command, check=True)
    with boot.open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise RuntimeError('GRUB output is not a PE image')
    docs = package/'HardwareCollector/docs'
    docs.mkdir()
    for name in ['LICENSE', 'NOTICE', 'THIRD_PARTY.md']:
        shutil.copyfile(HERE/name, docs/name)
    shutil.copyfile(HERE/'docs/usb.md', docs/'README.md')
    shutil.copyfile(HERE/'docs/design.md', docs/'design.md')
    manifest = {str(p.relative_to(package)): digest(p) for p in sorted(package.rglob('*')) if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    shutil.copyfile(HERE/'Install-Collector.ps1', output/'Install-Collector.ps1')
    shutil.copyfile(HERE/'README.md', output/'README.md')
    print('Package ready:', output)
    print('No physical disk was written. Use Install-Collector.ps1 after checking the target USB identity.')


if __name__ == '__main__':
    main()
