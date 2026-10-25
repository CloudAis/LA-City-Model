#!/usr/bin/env python3
"""Publish the final private delivery over authorized Git LFS transport.

Use this when the session can push Git/LFS but cannot upload Release attachments.
Large objects live on delivery-v1.0.0, leaving the default code branch lightweight.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, tempfile
import github_release_bundle as bundle

ROOT, WORK, CACHE = bundle.ROOT, bundle.WORK, bundle.CACHE
BRANCH = 'delivery-v1.0.0'
PREFIX = 'deliveries/v1.0.0/'
RECEIPTS = WORK / 'lfs_assets.json'
ENV = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_LFS_SKIP_SMUDGE': '0'}
GIT = ['git', '-c', 'credential.helper=!gh auth git-credential']


def git(*args, data=None, env=None):
    result = subprocess.run([*GIT, *args], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=ROOT, env=env or ENV)
    if result.returncode:
        raise RuntimeError('Git/LFS operation failed: ' + result.stderr.decode(errors='replace')[-1200:])
    return result.stdout


def receipts():
    return json.loads(RECEIPTS.read_text()) if RECEIPTS.exists() else {}


def pointer(row):
    return ('version https://git-lfs.github.com/spec/v1\noid sha256:' + row['sha256'] +
            '\nsize ' + str(row['bytes']) + '\n').encode()


class Download:
    def __init__(self, row, repo):
        self.folder = Path(tempfile.mkdtemp(prefix='lfs-readback-', dir=CACHE))
        command = [*GIT, '-c', f'lfs.url=https://github.com/{repo}.git/info/lfs',
                   '-c', 'lfs.storage=' + str(self.folder), 'lfs', 'smudge', row['name']]
        self.process = subprocess.Popen(command, cwd=ROOT, env=ENV, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.process.stdin.write(pointer(row))
        self.process.stdin.close()
        self.stdout, self.stderr = self.process.stdout, self.process.stderr

    def wait(self):
        code = self.process.wait()
        shutil.rmtree(self.folder)
        return code


def verify_object(row, repo):
    process = Download(row, repo)
    result, size = hashlib.sha256(), 0
    for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
        result.update(block)
        size += len(block)
    error = process.stderr.read().decode(errors='replace')
    if process.wait() or result.hexdigest() != row['sha256'] or size != row['bytes']:
        raise RuntimeError('Fresh remote LFS download differs: ' + row['name'] + error[-500:])


def publish_tree(repo):
    rows = receipts()
    CACHE.mkdir(parents=True, exist_ok=True)
    previous = subprocess.run(['git', 'rev-parse', '--verify', 'refs/heads/' + BRANCH],
                              cwd=ROOT, capture_output=True, text=True)
    parent = previous.stdout.strip() if previous.returncode == 0 else git('rev-parse', 'HEAD').decode().strip()
    # Build a separate index/tree; never check out or overwrite the author's files.
    with tempfile.TemporaryDirectory(prefix='delivery-index-', dir=CACHE) as folder:
        env = {**ENV, 'GIT_INDEX_FILE': str(Path(folder) / 'index')}
        git('read-tree', 'HEAD', env=env)
        attributes = (PREFIX + '*.part* filter=lfs diff=lfs merge=lfs -text\n' +
                      PREFIX + '*.zip filter=lfs diff=lfs merge=lfs -text\n').encode()
        items = {'.gitattributes': attributes}
        for row in rows.values():
            items[PREFIX + row['name']] = pointer(row) if row['transport'] == 'git_lfs' else bytes.fromhex(row['content_hex'])
        for path, data in items.items():
            oid = git('hash-object', '-w', '--stdin', data=data, env=env).decode().strip()
            git('update-index', '--add', '--cacheinfo', '100644', oid, path, env=env)
        tree = git('write-tree', env=env).decode().strip()
    commit = git('commit-tree', tree, '-p', parent,
                 data=('Store verified private delivery assets: ' + str(len(rows)) + '\n').encode()).decode().strip()
    git('update-ref', 'refs/heads/' + BRANCH, commit)
    git('push', 'github-la', commit + ':refs/heads/' + BRANCH)
    bundle.save('lfs_branch.json', {'repo': repo, 'branch': BRANCH, 'commit': commit,
                                  'files': len(rows), 'prefix': PREFIX})
    return commit


def upload_file(path, repo, tag):
    row = {'name': path.name, 'bytes': path.stat().st_size, 'sha256': bundle.digest(path)}
    rows = receipts()
    if path.name in rows:
        existing = rows[path.name]
        if existing['sha256'] != row['sha256'] or existing['bytes'] != row['bytes']:
            raise RuntimeError('Preserve changed published asset: ' + path.name)
        print('LFS_PREVIOUS_VERIFIED_ASSET_REUSED', path.name, flush=True)
        return existing
    large = path.suffix == '.zip' or '.tar.gz.part' in path.name
    row.update({'id': row['sha256'], 'transport': 'git_lfs' if large else 'git_blob'})
    if large:
        object_path = ROOT / '.git/lfs/objects' / row['sha256'][:2] / row['sha256'][2:4] / row['sha256']
        object_path.parent.mkdir(parents=True, exist_ok=True)
        created = not object_path.exists()
        if created:
            # Immutable LFS object shares bytes until upload; no duplicate ZIP on disk.
            os.link(path, object_path)
        elif bundle.digest(object_path) != row['sha256']:
            raise RuntimeError('Existing LFS object differs; preserve it')
        git('lfs', 'push', '--object-id', 'github-la', row['sha256'])
        verify_object(row, repo)
        if created:
            object_path.unlink()
    else:
        row['content_hex'] = path.read_bytes().hex()
    row['remote_download_verified'] = large
    rows[path.name] = row
    RECEIPTS.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    publish_tree(repo)
    print('GITHUB_LFS_AND_POINTER_VERIFIED', path.name, row['bytes'], flush=True)
    return row


def remote_rows(repo, tag):
    git('fetch', 'github-la', 'refs/heads/' + BRANCH + ':refs/remotes/github-la/' + BRANCH)
    remote_ref = 'refs/remotes/github-la/' + BRANCH
    rows = receipts()
    for row in rows.values():
        actual = git('show', remote_ref + ':' + PREFIX + row['name'])
        expected = pointer(row) if row['transport'] == 'git_lfs' else bytes.fromhex(row['content_hex'])
        if actual != expected:
            raise RuntimeError('Actual remote Git pointer/content differs: ' + row['name'])
    return list(rows.values())


def remote_download(oid, repo):
    row = next(r for r in receipts().values() if r['sha256'] == oid)
    return Download(row, repo)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['upload', 'verify', 'sync-tree'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', default='v1.0.0')
    args = parser.parse_args()
    if not bundle.api('repos/' + args.repo)['private']:
        raise SystemExit('Authorized destination must remain private')
    CACHE.mkdir(parents=True, exist_ok=True)
    bundle.upload_file, bundle.assets, bundle.download = upload_file, remote_rows, remote_download
    if args.action == 'upload':
        bundle.upload(args.repo, args.tag)
        report = json.loads((WORK / 'uploaded_assets.json').read_text())
        report.update({'transport': 'git_lfs_branch', 'branch': BRANCH})
        bundle.save('uploaded_assets.json', report)
    elif args.action == 'verify':
        bundle.verify(args.repo, args.tag)
        report = json.loads((WORK / 'remote_archive_check.json').read_text())
        report.update({'transport': 'git_lfs_branch', 'actual_remote_git_pointers_verified': True})
        bundle.save('remote_archive_check.json', report)
    else:
        publish_tree(args.repo)
