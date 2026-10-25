#!/usr/bin/env python3
"""Upload and independently stream-verify a private GitHub final delivery.

Requires authenticated gh. Keeps at most one128MiB archive part on local disk.
Does not change accepted model files or publish a draft automatically.
"""
from pathlib import Path, PurePosixPath
import argparse, gzip, hashlib, io, json, subprocess, tarfile, time

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / 'outputs/LA_Delivery'
WORK = ROOT / 'work/reports/github_publication'
CACHE = ROOT / 'work/cache/github_publication'
PART_BYTES = 128 * 1024 ** 2
INDEX_NAME = 'LA_Delivery_1.0_MANIFEST.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def api(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', endpoint], text=True))


def save(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def assets(repo, tag):
    # GitHub's tag lookup omits drafts, even when an authenticated owner can
    # list and upload to them. Resolve the authorized draft by its tag instead.
    for release in api(f'repos/{repo}/releases?per_page=100'):
        if release['tag_name'] == tag:
            return release['assets']
    raise RuntimeError('Release/draft not found for tag: ' + tag)


def download(asset_id, repo):
    return subprocess.Popen(['gh', 'api', f'repos/{repo}/releases/assets/{asset_id}',
                             '-H', 'Accept: application/octet-stream'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def verify_asset(row, repo, expected):
    process = download(row['id'], repo)
    result = hashlib.sha256()
    size = 0
    for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
        result.update(block)
        size += len(block)
    error = process.stderr.read().decode(errors='replace')
    if process.wait() != 0:
        raise RuntimeError('GitHub asset read failed: ' + error[:300])
    if result.hexdigest() != expected['sha256'] or size != expected['bytes']:
        raise RuntimeError('Remote bytes differ: ' + row['name'])
    return {'name': row['name'], 'asset_id': row['id'], 'bytes': size,
            'sha256': result.hexdigest(), 'remote_download_verified': True}


def upload_file(path, repo, tag):
    expected = {'name': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
    row = next((a for a in assets(repo, tag) if a['name'] == path.name), None)
    if row is None:
        for attempt in range(3):
            result = subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', repo],
                                    text=True, capture_output=True)
            row = next((a for a in assets(repo, tag) if a['name'] == path.name), None)
            if result.returncode == 0 and row is not None:
                break
            if attempt == 2:
                raise RuntimeError('Upload failed; existing assets preserved: ' + result.stderr[:400])
            time.sleep(2)
    verified = verify_asset(row, repo, expected)
    print('REMOTE_SHA256_VERIFIED', path.name, expected['bytes'], flush=True)
    return verified


class UploadParts(io.RawIOBase):
    def __init__(self, repo, tag):
        self.repo, self.tag = repo, tag
        self.current = None
        self.path = None
        self.size = 0
        self.rows = []
        self.archive_hash = hashlib.sha256()
        self.total = 0
        self.aborted = False

    def writable(self):
        return True

    def write(self, data):
        # gzip finalizes its buffer while unwinding an upload exception. Drop
        # only these cleanup bytes; keep the original failed part for recovery.
        if self.aborted:
            return len(data)
        data = memoryview(data)
        length = len(data)
        self.archive_hash.update(data)
        self.total += length
        while data:
            if self.current is None:
                self.path = CACHE / ('LA_Delivery_1.0.tar.gz.part%03d' % (len(self.rows) + 1))
                self.current = self.path.open('xb')
                self.size = 0
            amount = min(PART_BYTES - self.size, len(data))
            self.current.write(data[:amount])
            self.size += amount
            data = data[amount:]
            if self.size == PART_BYTES:
                self.finish_part()
        return length

    def finish_part(self):
        if self.current is None:
            return
        self.current.close()
        self.current = None
        print('UPLOAD_PART', self.path.name, self.size, flush=True)
        try:
            verified = upload_file(self.path, self.repo, self.tag)
        except BaseException:
            self.aborted = True
            raise
        self.rows.append(verified)
        save('parts_in_progress.json', {'parts': self.rows, 'complete': False})
        self.path.unlink()


def upload(repo, tag):
    CACHE.mkdir(parents=True, exist_ok=True)
    index_path = DELIVERY / 'metadata/DELIVERY_MANIFEST.json'
    index = json.loads(index_path.read_text())
    rows = index['files'] + [{'path': 'metadata/DELIVERY_MANIFEST.json',
                             'bytes': index_path.stat().st_size, 'sha256': digest(index_path)}]
    out = UploadParts(repo, tag)
    with gzip.GzipFile(filename='', mode='wb', compresslevel=5, fileobj=out, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT,
                          dereference=True) as archive:
            for number, row in enumerate(sorted(rows, key=lambda r: r['path'])):
                path = (DELIVERY / row['path']).resolve()
                if not path.is_relative_to(DELIVERY) or digest(path) != row['sha256']:
                    raise RuntimeError('Changed accepted delivery file: ' + row['path'])
                info = archive.gettarinfo(str(path), arcname='LA_Delivery/' + row['path'])
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = 0
                info.pax_headers = {}
                with path.open('rb') as source:
                    archive.addfile(info, source)
                if number % 2000 == 0:
                    print('ARCHIVED_ACTUAL_FILE', number, row['path'], flush=True)
    out.finish_part()
    metadata = {'version': '1.0.0', 'repo': repo, 'tag': tag, 'format': 'concatenated tar.gz',
                'archive_sha256': out.archive_hash.hexdigest(), 'archive_bytes': out.total,
                'file_count': len(rows), 'uncompressed_file_bytes': sum(r['bytes'] for r in rows),
                'delivery_manifest_sha256': digest(index_path),
                'parts': [{'name': r['name'], 'bytes': r['bytes'], 'sha256': r['sha256']} for r in out.rows],
                'source_data_and_historical_caches_included': False,
                'private_handoff_not_a_public_redistribution_license': True}
    save(INDEX_NAME, metadata)
    upload_file(WORK / INDEX_NAME, repo, tag)
    extras = []
    for name in ['LA_Local_Private_Viewer_1.0.zip', 'LA_Original_Materials_And_Tools_1.0.zip']:
        extras.append(upload_file(ROOT / 'outputs' / name, repo, tag))
    save('uploaded_assets.json', {'status': 'passed', 'parts': out.rows, 'other_assets': extras})


class RemoteParts(io.RawIOBase):
    def __init__(self, repo, rows, remote):
        self.repo, self.rows, self.remote = repo, iter(rows), remote
        self.process = None
        self.current_hash = None
        self.archive_hash = hashlib.sha256()
        self.row = None

    def readable(self):
        return True

    def read(self, size=-1):
        if size < 0:
            raise ValueError('Unbounded remote read')
        result = bytearray()
        while len(result) < size:
            if self.process is None:
                self.row = next(self.rows, None)
                if self.row is None:
                    break
                self.process = download(self.remote[self.row['name']]['id'], self.repo)
                self.current_hash = hashlib.sha256()
            block = self.process.stdout.read(size - len(result))
            if not block:
                error = self.process.stderr.read().decode(errors='replace')
                if self.process.wait() != 0 or self.current_hash.hexdigest() != self.row['sha256']:
                    raise RuntimeError('Remote part mismatch: ' + self.row['name'] + error[:200])
                self.process = None
                continue
            self.current_hash.update(block)
            self.archive_hash.update(block)
            result.extend(block)
        return bytes(result)


def verify(repo, tag):
    metadata = json.loads((WORK / INDEX_NAME).read_text())
    remote = {row['name']: row for row in assets(repo, tag)}
    stream = RemoteParts(repo, metadata['parts'], remote)
    expected_index = json.loads((DELIVERY / 'metadata/DELIVERY_MANIFEST.json').read_text())
    expected = {row['path']: row for row in expected_index['files']}
    expected['metadata/DELIVERY_MANIFEST.json'] = {'sha256': metadata['delivery_manifest_sha256'],
                                                'bytes': (DELIVERY / 'metadata/DELIVERY_MANIFEST.json').stat().st_size}
    seen = set()
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or path.parts[0] != 'LA_Delivery':
                raise RuntimeError('Unexpected remote archive member')
            relative = str(PurePosixPath(*path.parts[1:]))
            if relative not in expected or relative in seen:
                raise RuntimeError('Unexpected/duplicate remote file: ' + relative)
            source = archive.extractfile(member)
            result = hashlib.sha256()
            size = 0
            for block in iter(lambda: source.read(1024 * 1024), b''):
                result.update(block)
                size += len(block)
            if result.hexdigest() != expected[relative]['sha256'] or size != expected[relative]['bytes']:
                raise RuntimeError('Remote restored file differs: ' + relative)
            seen.add(relative)
            if len(seen) % 2000 == 0:
                print('REMOTE_ARCHIVE_FILES_VERIFIED', len(seen), flush=True)
    while stream.read(1024 * 1024):
        pass
    if seen != set(expected) or stream.archive_hash.hexdigest() != metadata['archive_sha256']:
        raise RuntimeError('Incomplete remote archive verification')
    save('remote_archive_check.json', {'status': 'passed', 'actual_github_assets_downloaded': True,
                                     'files_individually_verified': len(seen),
                                     'archive_sha256': stream.archive_hash.hexdigest(),
                                     'remote_part_count': len(metadata['parts']),
                                     'no_extra_full_archive_written_to_local_disk': True})
    print('FULL_REMOTE_DELIVERY_VERIFIED', len(seen), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['upload', 'verify'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', default='v1.0.0')
    args = parser.parse_args()
    repository = api('repos/' + args.repo)
    if not repository['private']:
        raise SystemExit('Full city publication requires the authorized private destination')
    (upload if args.action == 'upload' else verify)(args.repo, args.tag)
