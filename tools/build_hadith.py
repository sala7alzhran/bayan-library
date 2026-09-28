"""Builds the Bayan Hadith pack (hadith.db, SQLite with an FTS4 index) from fawazahmed0/hadith-api (Unlicense).

Usage: python build_hadith.py <dir with ara-<book>.json files> <out.db> [version]
The Arabic editions come from https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-<book>.min.json
"""
import json
import os
import re
import sqlite3
import sys

from arabic_fold import fold, index_text

# (id, Arabic book name, name used in "رواه …", order)
BOOKS = [
    ('nawawi', 'الأربعون النووية', '', 0),
    ('qudsi', 'الأحاديث القدسية الأربعون', '', 1),
    ('bukhari', 'صحيح البخاري', 'البخاري', 2),
    ('muslim', 'صحيح مسلم', 'مسلم', 3),
    ('abudawud', 'سنن أبي داود', 'أبو داود', 4),
    ('tirmidhi', 'جامع الترمذي', 'الترمذي', 5),
    ('nasai', 'سنن النسائي', 'النسائي', 6),
    ('ibnmajah', 'سنن ابن ماجه', 'ابن ماجه', 7),
    ('malik', 'موطأ مالك', 'مالك', 8),
    ('dehlawi', 'الأربعون للدهلوي', '', 9),
]
SAHIH = {'bukhari', 'muslim'}
# Collections that already give the hadith without the chain of narrators.
MATN_ONLY = {'nawawi', 'qudsi', 'dehlawi'}

GRADERS = {
    'Al-Albani': 'الألباني',
    'Shuaib Al Arnaut': 'شعيب الأرناؤوط',
    'Salim al-Hilali': 'سليم الهلالي',
}
GRADER_ORDER = ['Al-Albani', 'Shuaib Al Arnaut', 'Salim al-Hilali']
GRADE_WORDS = {
    'sahih': 'صحيح', 'hasan': 'حسن', 'daif': 'ضعيف', 'isnaad': 'الإسناد', 'sanad': 'الإسناد',
    'maqtu': 'مقطوع', 'muquf': 'موقوف', 'mauquf': 'موقوف', 'mutawatir': 'متواتر', 'shadh': 'شاذ',
    'munkar': 'منكر', 'mawdu': 'موضوع', 'mursal': 'مرسل', 'matn': 'المتن', 'lighairihi': 'لغيره', 'malool': 'معلول',
}


def grade_ar(grade):
    """An English grade ("Hasan Sahih", "Daif Isnaad", "Very Daif") in Arabic, or None when unknown."""
    g = grade.strip().lower().replace("'", '')
    words = g.split()
    very = 'very' in words
    words = [w for w in words if w not in ('very', 'hadith')]
    if not words or any(w not in GRADE_WORDS for w in words):
        return None
    out = [GRADE_WORDS[w] for w in words]
    # "Isnaad Sahih" / "Sanad Daif" read "صحيح الإسناد" / "ضعيف الإسناد".
    if out[0] == 'الإسناد' and len(out) > 1:
        out = out[1:2] + ['الإسناد'] + out[2:]
    if very:
        out.insert(1 if len(out) == 1 else 2, 'جدا')
    return ' '.join(out)


PROPHET_WORDS = {'النبي', 'للنبي', 'والنبي', 'بالنبي'}
MESSENGER = {'رسول', 'لرسول', 'ورسول', 'برسول'}
CONNECTORS = {'عن', 'حدثنا', 'حدثني', 'اخبرنا', 'اخبرني', 'انبانا', 'انباني', 'سمعت', 'سمع', 'حدثه', 'اخبره', 'حدثتني', 'حدثته'}
# "… بمثله", "بهذا الإسناد": a second chain for a hadith given before, with no text of its own.
LEAD_OUT = re.compile('(بهذا الاسناد|بمثله|بمثل حديث|نحوه|بنحوه|بمعناه|بهذا المعني|باسناده|بمثل معني|مثله)')
def prophet_at(f, i):
    return f[i] in PROPHET_WORDS or (f[i] in MESSENGER and i + 1 < len(f) and f[i + 1] in ('الله', 'اللهم'))


def is_connector(f, i):
    return f[i] in CONNECTORS


# "عن أبيه", "عن جده": the narrator is named by the one before, who is kept too.
RELATIVE = {'ابيه', 'ابيها', 'جده', 'جدها', 'عمه', 'امه', 'خاله', 'ابيهما'}
# A connector followed by these is not naming a narrator ("حدثه أن …", "سمعته يقول").
NOT_A_NAME = {'ان', 'انه', 'انها', 'قال', 'قالت', 'يقول', 'تقول', 'انهم', 'انهما'}
# The compiler's own remarks after the hadith ("قال أبو عيسى …", "قال أبو داود …").
COMPILERS = {'عيسي', 'داود', 'عبد'}


def matn(text):
    """The hadith from its last narrator on ("عن أبي هريرة قال: قال رسول الله ﷺ …"), without the chain before."""
    words = text.split()
    f = [fold(w) for w in words]
    # "ح": the chain switches to another one; the hadith follows the last chain.
    if 'ح' in f:
        last = len(f) - 1 - f[::-1].index('ح')
        if last + 1 < len(words):
            words, f = words[last + 1:], f[last + 1:]
    p = next((i for i in range(len(f)) if prophet_at(f, i)), None)
    start = None
    if p is not None:
        i = p - 1
        # "سمعت رسول الله", "عن النبي": that connector names the Prophet; the narrator is before it.
        if i >= 0 and is_connector(f, i):
            i -= 1
        while i >= 0:
            if is_connector(f, i):
                after = f[i + 1] if i + 1 < len(f) else ''
                if after not in NOT_A_NAME and after not in RELATIVE:
                    start = i
                    break
            i -= 1
    else:
        for i in range(int(len(words) * 0.7), -1, -1):
            if f[i] == 'عن' and (f[i + 1] if i + 1 < len(f) else '') not in RELATIVE:
                start = i
                break
    end = len(words)
    for j in range((p or 0) + 1, len(f) - 2):
        if f[j] == 'قال' and f[j + 1] == 'ابو' and f[j + 2] in COMPILERS:
            end = j
            break
        # Al-Tirmidhi's "وفي الباب عن …": other companions who narrated it.
        if f[j] == 'وفي' and f[j + 1] == 'الباب':
            end = j
            break
    if start is None or start + 1 >= end:
        return ' '.join(words[:end]).strip()
    # From the connector itself, word for word ("عَنْ أَبِي هُرَيْرَةَ", "سَمِعْتُ عُمَرَ بْنَ الْخَطَّابِ").
    return ' '.join(words[start:end])


def tidy(text):
    s = text
    for mark in ('‏', '‎', '‪', '‫', '‬'):
        s = s.replace(mark, '')
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('،.', '،').replace(' .', '.').replace(' ،', '،').replace('..', '.').replace(' :', ':')
    if s.count('"') % 2 == 1:
        # An unmatched quote mark: drop the last one so the others pair up.
        cut = s.rfind('"')
        s = s[:cut] + s[cut + 1:]
    if s.count('"'):
        parts = s.split('"')
        out = []
        for k, part in enumerate(parts):
            out.append(part)
            if k < len(parts) - 1:
                out.append('«' if k % 2 == 0 else '»')
        s = ''.join(out).replace('« ', '«').replace(' »', '»')
    return re.sub(r'\s+', ' ', s).strip()


def number(h):
    """The number Arabic references use (Muslim's "55.01" sub-numbers are cited as 55)."""
    n = h.get('arabicnumber') or h.get('hadithnumber')
    return str(n).split('.')[0]


def build(src, out, version):
    rows = {}
    order = []
    stats = {}
    for book, name, by, rank in BOOKS:
        data = json.load(open(os.path.join(src, f'ara-{book}.json'), encoding='utf-8'))['hadiths']
        kept = 0
        for h in data:
            text = (h.get('text') or '').strip()
            if not text:
                continue
            body = tidy(text if book in MATN_ONLY else matn(text))
            folded = fold(body)
            if len(folded) < (6 if book in MATN_ONLY else 25):
                continue
            if book not in MATN_ONLY and len(folded) < 160 and LEAD_OUT.search(folded):
                continue
            grade = grader = ''
            if book in SAHIH:
                grade = 'صحيح'
            else:
                by_name = {g['name']: g['grade'] for g in h.get('grades') or []}
                for who in GRADER_ORDER:
                    if who in by_name and grade_ar(by_name[who]):
                        grade, grader = grade_ar(by_name[who]), GRADERS[who]
                        break
            num = number(h)
            ref = (by, num, name)
            if folded in rows:
                rows[folded]['refs'].append(ref)
                continue
            try:
                n = int(float(num))
            except ValueError:
                n = 0
            rows[folded] = {'text': body, 'refs': [ref], 'grade': grade, 'grader': grader, 'rank': rank * 100000 + n}
            order.append(folded)
            kept += 1
        stats[book] = (len(data), kept)
    print(stats, 'total', len(order))

    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.executescript('''
        PRAGMA page_size = 4096;
        PRAGMA journal_mode = DELETE;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE hadith(id INTEGER PRIMARY KEY, rank INTEGER NOT NULL, text TEXT NOT NULL,
            source TEXT NOT NULL, reference TEXT NOT NULL, grade TEXT NOT NULL, grader TEXT NOT NULL);
        CREATE VIRTUAL TABLE hadith_fts USING fts4(content="", body);
    ''')
    for i, key in enumerate(order, 1):
        r = rows[key]
        _, num, name = r['refs'][0]
        # As it is quoted: "رواه البخاري (1) ومسلم (1907)"; a collection's own numbering otherwise.
        seen, parts = set(), []
        for b, n, _ in r['refs']:
            if b and b not in seen:
                seen.add(b)
                parts.append(f'{b} ({n})')
        reference = ('رواه ' + ' و'.join(parts)) if parts else f'{name} ({num})'
        db.execute('INSERT INTO hadith VALUES (?,?,?,?,?,?,?)',
                   (i, r['rank'], r['text'], f'{name} {num}', reference, r['grade'], r['grader']))
        db.execute('INSERT INTO hadith_fts(docid, body) VALUES (?, ?)', (i, index_text(key)))
    db.executemany('INSERT INTO meta VALUES (?, ?)', [
        ('kind', 'hadith'), ('version', version), ('count', str(len(order))),
        ('source', 'fawazahmed0/hadith-api (Unlicense)'),
    ])
    db.execute("INSERT INTO hadith_fts(hadith_fts) VALUES('optimize')")
    db.commit()
    db.execute('VACUUM')
    db.close()
    print('bytes', os.path.getsize(out))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '1')
