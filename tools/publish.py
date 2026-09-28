"""Publishes a rebuilt pack to the Bayan library repository: compresses it, uploads it as a GitHub release
("<pack>-<version>") and updates manifest.json, which the keyboard reads to offer the update.

Usage (from the repository's root, with the GitHub CLI signed in):
    python tools/publish.py hadith 2 path/to/hadith.db
Then commit and push manifest.json.
"""
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

REPO = 'sala7alzhran/bayan-library'
PACKS = ('hadith', 'poetry')


def main(pack, version, db_path):
    if pack not in PACKS:
        sys.exit(f'pack must be one of {PACKS}')
    version = int(version)
    db = sqlite3.connect(db_path)
    meta = dict(db.execute('SELECT key, value FROM meta'))
    db.close()
    if meta.get('kind') != pack or int(meta.get('version', 0)) != version:
        sys.exit(f'{db_path} is {meta.get("kind")} version {meta.get("version")}; rebuild it with version {version}')

    gz_path = f'{pack}.db.gz'
    with open(db_path, 'rb') as src, gzip.GzipFile(gz_path, 'wb', compresslevel=9, mtime=0) as out:
        shutil.copyfileobj(src, out)
    data = open(gz_path, 'rb').read()
    tag = f'{pack}-{version}'
    subprocess.run(['gh', 'release', 'create', tag, gz_path, '--repo', REPO, '--title', f'{pack} {version}',
                    '--notes', f'{pack} pack, version {version}'], check=True)

    manifest = json.load(open('manifest.json', encoding='utf-8'))
    manifest['packs'][pack] = {
        'version': version,
        'url': f'https://github.com/{REPO}/releases/download/{tag}/{pack}.db.gz',
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'installedBytes': os.path.getsize(db_path),
        'count': int(meta.get('count', 0)),
    }
    with open('manifest.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.remove(gz_path)
    print(json.dumps(manifest['packs'][pack], indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:4])
