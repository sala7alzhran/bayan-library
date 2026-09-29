# Bayan library packs

Offline Hadith and Arabic poetry packs for the **Bayan (بيان)** keyboard. The keyboard does not include them; you
download a pack from Bayan's settings, or from its Hadith or Poetry tool. After that it works fully offline: type a
few words and the matching hadiths or verses appear.

حزم الأحاديث والشعر العربي للوحة مفاتيح **بيان**. لا تأتي مع التطبيق، بل تُنزَّل من الإعدادات أو من أداة
الأحاديث أو الشعر. بعد تنزيلها تعمل دون إنترنت: اكتب كلمات من الحديث أو البيت فتظهر النتائج فوراً.

| Pack | What it holds | Source | License |
|------|---------------|--------|---------|
| Hadith (الأحاديث) | 33,000+ hadiths: Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, Sunan Ibn Majah, Muwatta Malik, al-Nawawi's Forty, forty Hadith Qudsi, al-Dehlawi's Forty. Each with its book and number, and its grade when known | [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) | The Unlicense (public domain) |
| Poetry (الشعر) | 200,000 verses by more than 1,500 poets, pre-Islamic to the early 20th century; 44,000 verses of wisdom (الحكمة والموعظة) marked, and 215 well-known verses of wisdom chosen for Bayan | [tahaio/arabicpoetry](https://huggingface.co/datasets/tahaio/arabicpoetry) (complete poems of 55 poets); [Mana](https://github.com/NoorBayan/Mana) by Noor Bayan (poems annotated with themes: wisdom poems, and public-domain modern poets) | MIT; CC BY 4.0 |

The packs are published as release files. `manifest.json` lists the current version of each pack with its size and
SHA-256; the keyboard checks the hash of what it downloads, and offers an update when the version here is newer.

## What was done to the texts

- **Hadith:** the Arabic text is kept word for word, with its diacritics. The long chain of narrators before the
  last narrator is left out, so a hadith starts at the companion ("عن أبي هريرة قال: قال رسول الله ﷺ …"), and
  the compiler's own remarks after it ("قال أبو عيسى …", "وفي الباب …") are left out too. Quotation marks around the
  Prophet's words are shown as « ». Entries that only give another chain for the previous hadith ("بمثله",
  "بهذا الإسناد") are skipped. A hadith found in several books with the same words is listed once, with all of its
  references ("رواه البخاري (1) ومسلم (1907)"). Numbers are the ones Arabic references use.
- **Grades:** al-Bukhari and Muslim are marked "صحيح". For the other books the grade is al-Albani's where the source
  has one (otherwise Shu'aib al-Arna'ut's, or Salim al-Hilali's for the Muwatta), with the grader's name.
- **Poetry:** verses as in the sources, first and second half, with the poet, the poem's title and its meter. From
  Mana: every poem whose themes are at least 30% wisdom and admonition (theme 2.6), and the poems of modern poets who
  died before 1955 (their work is in the public domain); poets of other modern or unknown eras are left out. Verses of
  wisdom are marked; `tools/famous_verses.txt` lists well-known verses of wisdom, found in the sources (a few by Ahmad
  Shawqi, Hafez Ibrahim and al-Shabbi are given there in full, as the sources cut those poems short).

Texts are for reference; check a hadith's grade in the scholarly sources before relying on it.

## Updating a pack

1. Edit or rebuild with the tools (Python 3):
   - `tools/build_hadith.py <dir with ara-<book>.json> hadith.db <version>` — the files come from
     `https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-<book>.min.json`
     (bukhari, muslim, abudawud, tirmidhi, nasai, ibnmajah, malik, nawawi, qudsi, dehlawi).
   - `tools/build_poetry.py Arabic_Poetry_Dataset.csv Mana.csv poetry.db <version>` — add poets to `tools/poets.txt`,
     well-known verses to `tools/famous_verses.txt`. Mana.csv is inside `corpus/Mana.rar` of NoorBayan/Mana. Needs NLTK.
2. `python tools/publish.py <hadith|poetry> <version> <file.db>` (GitHub CLI signed in) uploads the release and
   updates `manifest.json`.
3. Commit and push `manifest.json`. Keyboards offer the update the next time Bayan's library settings are opened.

## Pack format

SQLite 3 with an FTS4 index over the text folded for search (diacritics removed, أ/إ/آ → ا, ة → ه, ى → ي), plus
the words without a leading particle or article and each word's root (ISRI stemmer, marked "r": "تبسمك" → "rبسم"), so
a search finds other forms of a word. `docinfo` holds words per document and, for poetry, each verse's kind (1 wisdom,
2 well-known); `verse_start` indexes the first two words of each half of the verses of wisdom, for suggestions while
typing. Tables: `meta`, `hadith` or `poet`/`poem`/`verse`.

## Licenses

- Hadith data: fawazahmed0/hadith-api, released under The Unlicense (public domain).
- Poetry data: Mana (مَعنَى), Noor Bayan, https://github.com/NoorBayan/Mana, Creative Commons Attribution 4.0
  International; wisdom themes and many poems are from it.
- Poetry data: tahaio/arabicpoetry, MIT License, Copyright (c) tahaio:

  > Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  > documentation files (the "Software"), to deal in the Software without restriction, including without
  > limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
  > Software, and to permit persons to whom the Software is furnished to do so, subject to the following
  > conditions: The above copyright notice and this permission notice shall be included in all copies or
  > substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

- The tools in `tools/` are part of the Bayan project.
