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


def index_text(folded: str) -> str:
    """What the full-text index holds for a folded text: its words, then the bare forms of words with particles."""
    words = folded.split()
    extra = []
    seen = set(words)
    for w in words:
        for s in stems(w):
            if s not in seen:
                seen.add(s)
                extra.append(s)
    return ' '.join(words + extra)
