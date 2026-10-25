#!/usr/bin/env python3
"""Restore a GitHub Release split tar.gz without making a second joined archive.

Python3.10+; standard library only. Existing files are compared and preserved.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, io, json, os, tarfile


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


class Parts(io.RawIOBase):
    def __init__(self, folder, manifest):
        self.folder, self.rows = folder, iter(manifest['parts'])
        self.current = None
        self.part_hash = None
        self.archive_hash = hashlib.sha256()
        self.row = None

    def readable(self):
        return True

    def read(self, size=-1):
        if size < 0:
            raise ValueError('Streaming reads must have a bounded size')
        result = bytearray()
        while len(result) < size:
            if self.current is None:
                self.row = next(self.rows, None)
                if self.row is None:
                    break
                name = self.row['name']
                if Path(name).name != name:
                    raise ValueError('Invalid part filename')
                path = self.folder / name
                if path.stat().st_size != self.row['bytes']:
                    raise ValueError('Part size differs: ' + name)
                self.current = path.open('rb')
                self.part_hash = hashlib.sha256()
            block = self.current.read(size - len(result))
            if not block:
                self.current.close()
                self.current = None
                if self.part_hash.hexdigest() != self.row['sha256']:
                    raise ValueError('Part checksum differs: ' + self.row['name'])
                continue
            self.part_hash.update(block)
            self.archive_hash.update(block)
            result.extend(block)
        return bytes(result)


def restore(parts_dir, output):
    metadata = json.loads((parts_dir / 'LA_Delivery_1.0_MANIFEST.json').read_text())
    # Check all downloaded bytes before writing any output files.
    for row in metadata['parts']:
        name = row['name']
        if Path(name).name != name:
            raise ValueError('Invalid part filename')
        path = parts_dir / name
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Missing or changed downloaded part: ' + name)
    stream = Parts(parts_dir, metadata)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    created = unchanged = 0
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'LA_Delivery' or not member.isfile():
                raise ValueError('Unexpected archive member: ' + member.name)
            target = (output / Path(*path.parts)).resolve()
            if not target.is_relative_to(output):
                raise ValueError('Archive path leaves output directory')
            source = archive.extractfile(member)
            if target.exists():
                expected = hashlib.sha256()
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    expected.update(block)
                if digest(target) != expected.hexdigest():
                    raise ValueError('Preserve changed existing file: ' + str(target))
                unchanged += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.github-restore-partial')
            created_temporary = False
            try:
                with temporary.open('xb') as dest:
                    created_temporary = True
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        dest.write(block)
                os.chmod(temporary, member.mode & 0o777)
                os.replace(temporary, target)
            except BaseException:
                if created_temporary and temporary.exists():
                    temporary.unlink()
                raise
            created += 1
    while stream.read(1024 * 1024):
        pass
    if stream.archive_hash.hexdigest() != metadata['archive_sha256']:
        raise ValueError('Combined archive checksum differs')
    delivery = output / 'LA_Delivery'
    index = delivery / 'metadata/DELIVERY_MANIFEST.json'
    if digest(index) != metadata['delivery_manifest_sha256']:
        raise ValueError('Delivery manifest differs')
    manifest = json.loads(index.read_text())
    for row in manifest['files']:
        path = (delivery / row['path']).resolve()
        if not path.is_relative_to(delivery) or digest(path) != row['sha256']:
            raise ValueError('Restored file differs: ' + row['path'])
    print(json.dumps({'status': 'passed', 'created_files': created, 'matching_existing_files': unchanged,
                      'delivery_files_verified': len(manifest['files']), 'path': str(delivery)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parts-dir', type=Path, default=Path('downloads'))
    parser.add_argument('--output', type=Path, default=Path('outputs'))
    args = parser.parse_args()
    restore(args.parts_dir, args.output)
