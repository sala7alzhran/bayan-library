"""Builds the Bayan poetry pack (poetry.db, SQLite with an FTS4 index) from tahaio/arabicpoetry (MIT), classical
Arabic poetry from the pre-Islamic to the Ottoman era, for the poets listed in poets.txt.

Usage: python build_poetry.py <Arabic_Poetry_Dataset.csv> <out.db> [version]
The dataset: https://huggingface.co/datasets/tahaio/arabicpoetry
"""
import csv
import os
import re
import sqlite3
import sys

from arabic_fold import fold, index_text

HERE = os.path.dirname(os.path.abspath(__file__))
SPACES = re.compile(r'\s+')


def poets():
    out = []
    for line in open(os.path.join(HERE, 'poets.txt'), encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        source, _, shown = line.partition('|')
        out.append((source.strip(), (shown or source).strip()))
    return out


def meter(tags):
    for tag in tags.split(','):
        tag = tag.strip()
        if tag.startswith('بحر '):
            return tag
    return ''


def clean(line):
    return SPACES.sub(' ', line.replace('‏', '').replace('‎', '')).strip(' *-')


def build(src, out, version):
    csv.field_size_limit(10 ** 9)
    wanted = poets()
    rank = {source: i for i, (source, _) in enumerate(wanted)}
    poems = {source: [] for source, _ in wanted}
    eras = {}
    for row in csv.DictReader(open(src, encoding='utf-8')):
        name = row['poet_name'].strip()
        if name in poems:
            poems[name].append(row)
            eras[name] = row['poet_era'].strip()
    missing = [s for s, _ in wanted if not poems[s]]
    if missing:
        sys.exit(f'not in the dataset: {missing}')

    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.executescript('''
        PRAGMA page_size = 4096;
        PRAGMA journal_mode = DELETE;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE poet(id INTEGER PRIMARY KEY, name TEXT NOT NULL, era TEXT NOT NULL);
        CREATE TABLE poem(id INTEGER PRIMARY KEY, poet INTEGER NOT NULL, title TEXT NOT NULL, meter TEXT NOT NULL);
        CREATE TABLE verse(id INTEGER PRIMARY KEY, poem INTEGER NOT NULL, first TEXT NOT NULL, second TEXT NOT NULL);
        CREATE INDEX verse_poem ON verse(poem);
        CREATE INDEX poem_poet ON poem(poet);
        CREATE VIRTUAL TABLE verse_fts USING fts4(content="", body);
    ''')
    verse_id = poem_id = 0
    chars = 0
    for poet_id, (source, shown) in enumerate(wanted, 1):
        db.execute('INSERT INTO poet VALUES (?,?,?)', (poet_id, shown, eras[source]))
        for row in poems[source]:
            lines = [clean(l) for l in row['poem_text'].split('\n')]
            lines = [l for l in lines if fold(l)]
            if not lines:
                continue
            poem_id += 1
            db.execute('INSERT INTO poem VALUES (?,?,?,?)', (poem_id, poet_id, clean(row['poem_title']), meter(row['poem_tags'])))
            # The lines alternate: first half of a verse (صدر), second half (عجز).
            for k in range(0, len(lines), 2):
                first = lines[k]
                second = lines[k + 1] if k + 1 < len(lines) else ''
                verse_id += 1
                chars += len(first) + len(second)
                db.execute('INSERT INTO verse VALUES (?,?,?,?)', (verse_id, poem_id, first, second))
                db.execute('INSERT INTO verse_fts(docid, body) VALUES (?, ?)', (verse_id, index_text(fold(first + ' ' + second))))
    db.executemany('INSERT INTO meta VALUES (?, ?)', [
        ('kind', 'poetry'), ('version', version), ('count', str(verse_id)), ('poets', str(len(wanted))),
        ('source', 'tahaio/arabicpoetry (MIT)'),
    ])
    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('optimize')")
    db.commit()
    db.execute('VACUUM')
    db.close()
    print('poets', len(wanted), 'poems', poem_id, 'verses', verse_id, 'chars', chars, 'bytes', os.path.getsize(out))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '1')
