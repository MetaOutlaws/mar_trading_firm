"""Publish the two exact owner-authorized checkpoints as GitHub release assets.

Requires an already authenticated GitHub CLI. Default only verifies local files.
No secret input, token printing, overwrite, deletion or change to default branch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = 'MetaOutlaws/mar_trading_firm'
TAG = 'research-checkpoints-20261006'
TARGET = '2b1b77825d48e655cb23dae3ad6f092393b1de47'
ASSETS = {
    'MAR_research_checkpoint_20261006.zip': (344597378, '7d357d4b5176d8190ee8efdd42fb3a6bd02a0b2c94262dc8b04ea04c49d9dc92'),
    'MAR_entry_discovery_checkpoint_20261006.zip': (334164151, '8667f9ffa8085e6c241f8e23bdba994154a8cf67b54c343aa3d28143cd1bd1cc'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def gh(*args, missing_ok=False):
    p = subprocess.run(['gh', *args], text=True, capture_output=True)
    if p.returncode:
        if missing_ok and 'HTTP 404' in p.stderr:
            return None
        raise RuntimeError('GitHub command failed: ' + p.stderr.strip())
    return p.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    directory = args.directory.resolve(strict=True)
    for name, (size, sha) in ASSETS.items():
        path = directory/name
        if path.stat().st_size != size or digest(path) != sha:
            raise RuntimeError('Wrong checkpoint bytes: ' + name)
    if not args.apply:
        print(json.dumps({'status': 'local_hashes_verified', 'release_upload_performed': False,
                          'repository': REPO, 'tag': TAG, 'assets': list(ASSETS)}, indent=2))
        return
    if not shutil.which('gh'):
        raise RuntimeError('Install GitHub CLI in the operator environment and use existing authentication')
    # A 404 on a private release must not hide lack of repository access.
    repo = json.loads(gh('api', 'repos/'+REPO))
    if repo.get('full_name') != REPO or not repo.get('permissions', {}).get('push'):
        raise RuntimeError('Authenticated repository write access is required')
    endpoint = 'repos/'+REPO+'/releases/tags/'+TAG
    raw = gh('api', endpoint, missing_ok=True)
    if raw is None:
        notes = ('Exact historical research archives requested by Brian on 8 October 2026.\n'
                 'These contain 6 October snapshots; deployment guidance inside is historical.\n'
                 'Read current PR99/PR101 GROK_START_HERE.md for the latest approved paper rule.\n\n'
                 + '\n'.join(sha+'  '+name for name, (_, sha) in ASSETS.items())+'\n')
        with tempfile.TemporaryDirectory() as td:
            note_path = Path(td)/'notes.md'; note_path.write_text(notes)
            gh('release', 'create', TAG, '--repo', REPO, '--target', TARGET,
               '--title', 'MAR research checkpoints — 6 October 2026', '--notes-file', str(note_path), '--latest=false')
        raw = gh('api', endpoint)
    release = json.loads(raw)
    if release.get('draft'):
        raise RuntimeError('Existing release is a draft; inspect it before publication')
    existing = {a['name']: a for a in release['assets']}
    for name in ASSETS:
        if name not in existing:
            gh('release', 'upload', TAG, str(directory/name), '--repo', REPO)
    # Read back both remote files, including any that already existed; never clobber.
    verified = []
    with tempfile.TemporaryDirectory() as td:
        for name, (size, sha) in ASSETS.items():
            gh('release', 'download', TAG, '--repo', REPO, '--pattern', name, '--dir', td)
            remote = Path(td)/name
            if remote.stat().st_size != size or digest(remote) != sha:
                raise RuntimeError('Remote asset differs; nothing overwritten: ' + name)
            verified.append(name)
    release = json.loads(gh('api', endpoint))
    result = {'status': 'release_assets_verified', 'release_url': release['html_url'],
              'assets': [dict(name=a['name'], url=a['browser_download_url']) for a in release['assets'] if a['name'] in verified]}
    (directory/'RELEASE_UPLOAD_VERIFIED.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
