"""Arabic folding shared by the pack builders; mirrors com.nexakey.text.SearchFold (and PackSearch.words)."""
import re

MARKS = re.compile('[ً-ٰٟۖ-ۭـ]')
LETTERS = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',  # hamza forms -> alef
    'ة': 'ه',  # taa marbuta -> haa
    'ى': 'ي', 'ئ': 'ي',  # alef maqsura, yaa hamza -> yaa
    'ؤ': 'و',  # waw hamza -> waw
    'ی': 'ي', 'ک': 'ك',  # Persian yeh, keheh
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
})
NON_LETTER = re.compile('[^ء-ي0-9a-z]+')


def fold(text: str) -> str:
    """Folded words separated by single spaces: diacritics dropped, letter variants merged, no punctuation."""
    s = MARKS.sub('', text).translate(LETTERS).lower()
    return NON_LETTER.sub(' ', s).strip()


def stems(word: str):
    """The word without a leading particle or article, so a search for the bare word still finds it:
    "بالنيات" -> "النيات", "نيات"; "للناس" -> "الناس", "ناس"; "وقال" -> "قال". At least three letters are left."""
    out = []
    for p in ('وال', 'فال', 'بال', 'كال', 'لل', 'ال', 'و', 'ف', 'ب', 'ل'):
        if word.startswith(p) and len(word) - len(p) >= 3:
            out.append(word[len(p):])
    for p in ('و', 'ف', 'ب', 'ك'):
        if word.startswith(p + 'ال') and len(word) >= 6:
            out.append(word[1:])
    if word.startswith('لل') and len(word) >= 5:
        out.append('ال' + word[2:])
    return [w for w in dict.fromkeys(out) if w != word]


_ISRI = None


def root(word: str) -> str:
    """The word's root by the ISRI stemmer (NLTK), run on the folded word; the keyboard runs the same algorithm
    (com.nexakey.text.ArabicRoot) on what is typed."""
    global _ISRI
    if _ISRI is None:
        from nltk.stem.isri import ISRIStemmer
        _ISRI = ISRIStemmer()
    return _ISRI.stem(word)


ROOT_MARK = 'r'


def index_text(folded: str) -> str:
    """What the full-text index holds for a folded text: its words, the bare forms of words with particles, and
    each word's root marked with "r" ("تبسمك" -> "rبسم"), so a search finds other forms of the same root."""
    words = folded.split()
    extra = []
    seen = set(words)
    for w in words:
        forms = stems(w)
        r = root(w) if len(w) >= 3 else ''
        if len(r) >= 2:
            forms.append(ROOT_MARK + r)
        for s in forms:
            if s not in seen:
                seen.add(s)
                extra.append(s)
    return ' '.join(words + extra)
