"""Builds the Bayan poetry pack (poetry.db, SQLite with an FTS4 index).

Sources:
- tahaio/arabicpoetry (MIT): the complete poems of the poets in poets.txt (pre-Islamic to Ottoman era).
- Mana, NoorBayan/Mana (CC BY 4.0): poems annotated with themes. Taken from it: every poem whose theme is wisdom
  and admonition (2.6, at least 30%) and every poem by the modern poets in PD_MODERN (died before 1955, so in the
  public domain), all from classical eras or those modern poets only (other modern poets' work is not public domain).
- famous_verses.txt: well-known verses of wisdom chosen for Bayan, found in the two corpora above.

Each verse has a kind: 2 well-known (famous_verses.txt), 1 wisdom, 0 other. Wisdom and well-known verses are
offered as suggestions while typing (table verse_start) and come first in search.

Usage: python build_poetry.py <Arabic_Poetry_Dataset.csv> <Mana.csv> <out.db> [version]
"""
import ast
import csv
import os
import re
import sqlite3
import sys
from collections import defaultdict

from arabic_fold import MARKS, fold, index_text

HERE = os.path.dirname(os.path.abspath(__file__))
SPACES = re.compile(r'\s+')
WISDOM_THEME = '2.6'
WISDOM_SHARE = 30
PD_MODERN = [
    'أحمد شوقي', 'حافظ إبراهيم', 'أبو القاسم الشابي', 'معروف الرصافي', 'محمود سامي البارودي', 'خليل مطران',
    'جميل صدقي الزهاوي', 'أحمد محرم', 'علي محمود طه', 'إسماعيل صبري', 'عائشة التيمورية', 'جبران خليل جبران',
    'ولي الدين يكن', 'عبد المحسن الكاظمي', 'حفني ناصف', 'إبراهيم اليازجي', 'ناصيف اليازجي', 'أحمد الكاشف',
    'فوزي المعلوف', 'أحمد فارس الشدياق', 'حسن حسني الطويراني', 'عبد الله فكري', 'أحمد زكي أبو شادي', 'علي الجارم',
    'مصطفى صادق الرافعي', 'شكيب أرسلان', 'محمد عبد المطلب', 'عبد الحميد الرافعي', 'أمين الريحاني',
]
TAHAIO_WISDOM_TAGS = ('قصائد حكمة', 'قصائد نصيحة', 'قصائد صبر')


def name_key(name):
    return fold(name).replace(' ', '')


def poets_list():
    out = []
    for line in open(os.path.join(HERE, 'poets.txt'), encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        source, _, shown = line.partition('|')
        out.append((source.strip(), (shown or source).strip()))
    return out


def famous_list():
    out = []
    for line in open(os.path.join(HERE, 'famous_verses.txt'), encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        words, _, poet = line.partition('|')
        out.append((words.strip(), poet.strip()))
    return out


def clean(line):
    return SPACES.sub(' ', line.replace('‏', '').replace('‎', '')).strip(' *-')


def pairs(lines):
    lines = [clean(l) for l in lines]
    lines = [l for l in lines if fold(l)]
    return [(lines[k], lines[k + 1] if k + 1 < len(lines) else '') for k in range(0, len(lines), 2)]


def meter(tags):
    for tag in tags.split(','):
        tag = tag.strip()
        if tag.startswith('بحر '):
            return tag
    return ''


class Poem:
    def __init__(self, poet, era, title, meter, verses, kind):
        self.poet, self.era, self.title, self.meter, self.verses = poet, era, title, meter, verses
        self.kinds = [kind] * len(verses)


def load(tahaio_path, mana_path):
    csv.field_size_limit(10 ** 9)
    wanted = poets_list()
    shown = {src: disp for src, disp in wanted}
    rank = {src: i for i, (src, _) in enumerate(wanted)}
    pack, extra = [], []            # poems in the pack; other complete poems (only to find well-known verses)
    for row in csv.DictReader(open(tahaio_path, encoding='utf-8')):
        name = row['poet_name'].strip()
        wise = any(t in row['poem_tags'] for t in TAHAIO_WISDOM_TAGS)
        poem = Poem(shown.get(name, name), row['poet_era'].strip(), clean(row['poem_title']), meter(row['poem_tags']),
                    pairs(row['poem_text'].split('\n')), 1 if wise else 0)
        if name in shown or wise:
            poem.rank = rank.get(name, len(wanted))
            pack.append(poem)
        else:
            extra.append(poem)
    missing = [s for s in shown if not any(p.poet == shown[s] for p in pack)]
    if missing:
        sys.exit(f'not in the dataset: {missing}')

    # Mana: eras 1-11 are classical; era 12 (modern) and 0 (unknown) only for listed public-domain poets or for
    # names that are classical poets elsewhere in the corpus.
    rows = list(csv.DictReader(open(mana_path, encoding='utf-16'), delimiter='\t'))
    classical = {name_key(r['poet_name']) for r in rows if r['poet_era'].isdigit() and 1 <= int(r['poet_era']) <= 11}
    modern = {name_key(n) for n in PD_MODERN}
    display = defaultdict(lambda: defaultdict(int))
    for r in rows:
        display[name_key(r['poet_name'])][MARKS.sub('', r['poet_name']).strip()] += 1
    known = {name_key(p.poet): p.poet for p in pack}
    known.update({name_key(n): n for n in PD_MODERN})
    eras = {1: 'العصر الجاهلي', 2: 'العصر الإسلامي', 3: 'المخضرمون', 4: 'العصر الأموي', 5: 'العصر العباسي', 6: 'العصر الأندلسي',
            7: 'عصر ما بين الدولتين', 8: 'العصر الأيوبي', 9: 'العصر المملوكي', 10: 'العصر الفاطمي', 11: 'العصر العثماني', 12: 'العصر الحديث'}
    for r in rows:
        k = name_key(r['poet_name'])
        era = int(r['poet_era']) if r['poet_era'].isdigit() else 0
        if not (1 <= era <= 11 or k in classical or k in modern):
            continue
        themes = ast.literal_eval(r['themes'])
        shares = ast.literal_eval(r['percentages'])
        share = sum(p for t, p in zip(themes, shares) if t.startswith(WISDOM_THEME))
        name = known.get(k) or max(display[k].items(), key=lambda kv: kv[1])[0]
        poem = Poem(name, eras.get(era, 'العصر الحديث' if k in modern else ''), clean(r['poem_title']), '',
                    pairs(ast.literal_eval(r['verses'])), 1 if share >= WISDOM_SHARE else 0)
        if share >= WISDOM_SHARE or k in modern:
            poem.rank = len(wanted) + (0 if k in modern else 1)
            pack.append(poem)
        else:
            extra.append(poem)
    return pack, extra


def mark_famous(pack, extra):
    """Finds each well-known verse; one found outside the pack is added as a poem of its own."""
    starts = defaultdict(list)
    for group in (pack, extra):
        for poem in group:
            for i, (a, b) in enumerate(poem.verses):
                for half in (a, b):
                    w = fold(half).split()
                    if len(w) >= 2:
                        starts[' '.join(w[:2])].append((poem, i, half))
    in_pack = {id(p) for p in pack}
    added, lost = 0, []
    for words, poet in famous_list():
        given = None
        if ' ... ' in words:
            given = tuple(h.strip() for h in words.split(' ... ', 1))
            words = given[0]
        want = fold(words).split()
        hits = [(p, i) for p, i, half in starts.get(' '.join(want[:2]), []) if fold(half).split()[:len(want)] == want]
        if not hits:
            # Remembered a little differently: the first three words, by that poet.
            pk = name_key(poet)
            hits = [(p, i) for p, i, half in starts.get(' '.join(want[:2]), [])
                    if fold(half).split()[:3] == want[:3] and (pk in name_key(p.poet) or name_key(p.poet) in pk)]
        if not hits and given:
            single = Poem(poet, 'العصر الحديث', '', '', [given], 2)
            single.rank = -1
            pack.append(single)
            in_pack.add(id(single))
            added += 1
            continue
        if not hits:
            lost.append(words)
            continue
        pk = name_key(poet)
        hits.sort(key=lambda h: (pk not in name_key(h[0].poet) and name_key(h[0].poet) not in pk, id(h[0]) not in in_pack))
        poem, i = hits[0]
        if id(poem) in in_pack:
            poem.kinds[i] = 2
        else:
            single = Poem(poem.poet, poem.era, poem.title, poem.meter, [poem.verses[i]], 2)
            single.rank = -1
            pack.append(single)
            in_pack.add(id(single))
            added += 1
    print('well-known verses: found', len(famous_list()) - len(lost), 'added from outside the pack', added)
    if lost:
        print('not found:', lost)


def build(tahaio_path, mana_path, out, version):
    pack, extra = load(tahaio_path, mana_path)
    mark_famous(pack, extra)
    pack.sort(key=lambda p: p.rank)
    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.executescript('''
        PRAGMA page_size = 4096;
        PRAGMA journal_mode = DELETE;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE docinfo(key TEXT PRIMARY KEY, data BLOB NOT NULL);
        CREATE TABLE poet(id INTEGER PRIMARY KEY, name TEXT NOT NULL, era TEXT NOT NULL);
        CREATE TABLE poem(id INTEGER PRIMARY KEY, poet INTEGER NOT NULL, title TEXT NOT NULL, meter TEXT NOT NULL);
        CREATE TABLE verse(id INTEGER PRIMARY KEY, poem INTEGER NOT NULL, first TEXT NOT NULL, second TEXT NOT NULL, kind INTEGER NOT NULL);
        CREATE TABLE verse_start(key TEXT NOT NULL, verse INTEGER NOT NULL);
        CREATE VIRTUAL TABLE verse_fts USING fts4(content="", body);
    ''')
    poet_ids, seen = {}, set()
    verse_id = poem_id = 0
    lengths, kinds = bytearray([0]), bytearray([0])
    for poem in pack:
        rows = []
        for (a, b), kind in zip(poem.verses, poem.kinds):
            key = fold(a + ' ' + b)
            if key in seen:
                continue
            seen.add(key)
            rows.append((a, b, kind))
        if not rows:
            continue
        if poem.poet not in poet_ids:
            poet_ids[poem.poet] = len(poet_ids) + 1
            db.execute('INSERT INTO poet VALUES (?,?,?)', (poet_ids[poem.poet], poem.poet, poem.era))
        poem_id += 1
        db.execute('INSERT INTO poem VALUES (?,?,?,?)', (poem_id, poet_ids[poem.poet], poem.title, poem.meter))
        for a, b, kind in rows:
            verse_id += 1
            folded = fold(a + ' ' + b)
            db.execute('INSERT INTO verse VALUES (?,?,?,?,?)', (verse_id, poem_id, a, b, kind))
            db.execute('INSERT INTO verse_fts(docid, body) VALUES (?, ?)', (verse_id, index_text(folded)))
            lengths.append(min(255, len(folded.split())))
            kinds.append(kind)
            if kind:
                for half in (a, b):
                    w = fold(half).split()
                    if len(w) >= 2:
                        db.execute('INSERT INTO verse_start VALUES (?, ?)', (w[0] + ' ' + w[1], verse_id))
    famous_out = os.environ.get('FAMOUS_OUT')
    if famous_out:
        with open(famous_out, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# Well-known verses of wisdom (tools/packs/famous_verses.txt), texts from tahaio/arabicpoetry (MIT),\n')
            f.write('# Mana (CC BY 4.0) or public-domain modern poets. first<TAB>second<TAB>poet\n')
            for a, b, poet in db.execute('SELECT v.first, v.second, p.name FROM verse v JOIN poem m ON m.id = v.poem '
                                         'JOIN poet p ON p.id = m.poet WHERE v.kind = 2 ORDER BY v.id'):
                f.write(f'{a}\t{b}\t{poet}\n')
    db.execute('CREATE INDEX verse_poem ON verse(poem)')
    db.execute('CREATE INDEX poem_poet ON poem(poet)')
    db.execute('CREATE INDEX verse_start_key ON verse_start(key)')
    db.executemany('INSERT INTO docinfo VALUES (?, ?)', [('lengths', bytes(lengths)), ('kinds', bytes(kinds))])
    db.executemany('INSERT INTO meta VALUES (?, ?)', [
        ('kind', 'poetry'), ('version', version), ('count', str(verse_id)), ('poets', str(len(poet_ids))),
        ('wisdom', str(sum(1 for k in kinds[1:] if k))),
        ('source', 'tahaio/arabicpoetry (MIT); Mana, NoorBayan/Mana (CC BY 4.0)'),
    ])
    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('optimize')")
    db.commit()
    db.execute('VACUUM')
    db.close()
    print('poets', len(poet_ids), 'poems', poem_id, 'verses', verse_id, 'wisdom', sum(1 for k in kinds[1:] if k == 1),
          'well-known', sum(1 for k in kinds[1:] if k == 2), 'bytes', os.path.getsize(out))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else '1')
