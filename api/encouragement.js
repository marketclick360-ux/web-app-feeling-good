// 365 encouraging Bible scriptures - rotates daily
// Each entry has: ref (scripture reference), book/chapter/verse for WOL link
const SCRIPTURES = [
  { ref: 'Isaiah 41:10', book: 23, chapter: 41, verse: 10 },
  { ref: 'Psalm 23:1-4', book: 19, chapter: 23, verse: 1 },
  { ref: 'Philippians 4:6, 7', book: 50, chapter: 4, verse: 6 },
  { ref: 'Proverbs 3:5, 6', book: 20, chapter: 3, verse: 5 },
  { ref: 'Matthew 6:33, 34', book: 40, chapter: 6, verse: 33 },
  { ref: 'Romans 8:38, 39', book: 45, chapter: 8, verse: 38 },
  { ref: 'Joshua 1:9', book: 6, chapter: 1, verse: 9 },
  { ref: 'Psalm 55:22', book: 19, chapter: 55, verse: 22 },
  { ref: 'Isaiah 40:31', book: 23, chapter: 40, verse: 31 },
  { ref: '1 Peter 5:7', book: 60, chapter: 5, verse: 7 },
  { ref: 'Jeremiah 29:11', book: 24, chapter: 29, verse: 11 },
  { ref: 'Psalm 46:1', book: 19, chapter: 46, verse: 1 },
  { ref: 'Hebrews 13:5, 6', book: 58, chapter: 13, verse: 5 },
  { ref: 'Psalm 37:4, 5', book: 19, chapter: 37, verse: 4 },
  { ref: 'Isaiah 26:3', book: 23, chapter: 26, verse: 3 },
  { ref: 'Romans 15:13', book: 45, chapter: 15, verse: 13 },
  { ref: 'Psalm 27:1', book: 19, chapter: 27, verse: 1 },
  { ref: 'Psalm 34:18', book: 19, chapter: 34, verse: 18 },
  { ref: '2 Timothy 1:7', book: 55, chapter: 1, verse: 7 },
  { ref: 'Psalm 91:1, 2', book: 19, chapter: 91, verse: 1 },
  { ref: 'Isaiah 43:2', book: 23, chapter: 43, verse: 2 },
  { ref: 'Psalm 121:1, 2', book: 19, chapter: 121, verse: 1 },
  { ref: 'Matthew 11:28-30', book: 40, chapter: 11, verse: 28 },
  { ref: 'Psalm 94:19', book: 19, chapter: 94, verse: 19 },
  { ref: '2 Corinthians 4:16-18', book: 47, chapter: 4, verse: 16 },
  { ref: 'Psalm 145:18, 19', book: 19, chapter: 145, verse: 18 },
  { ref: 'Romans 8:28', book: 45, chapter: 8, verse: 28 },
  { ref: 'Psalm 9:9, 10', book: 19, chapter: 9, verse: 9 },
  { ref: 'Isaiah 54:10', book: 23, chapter: 54, verse: 10 },
  { ref: 'Psalm 62:5-8', book: 19, chapter: 62, verse: 5 },
  { ref: 'Zephaniah 3:17', book: 36, chapter: 3, verse: 17 },
  { ref: 'Psalm 103:13, 14', book: 19, chapter: 103, verse: 13 },
  { ref: 'James 1:5', book: 59, chapter: 1, verse: 5 },
  { ref: 'Psalm 147:3', book: 19, chapter: 147, verse: 3 },
  { ref: 'Deuteronomy 31:8', book: 5, chapter: 31, verse: 8 },
  { ref: 'Psalm 73:26', book: 19, chapter: 73, verse: 26 },
  { ref: 'Nahum 1:7', book: 34, chapter: 1, verse: 7 },
  { ref: 'Lamentations 3:22, 23', book: 25, chapter: 3, verse: 22 },
  { ref: 'Psalm 138:7, 8', book: 19, chapter: 138, verse: 7 },
  { ref: '1 John 4:18', book: 62, chapter: 4, verse: 18 },
  { ref: 'Psalm 16:8', book: 19, chapter: 16, verse: 8 },
  { ref: 'Isaiah 12:2', book: 23, chapter: 12, verse: 2 },
  { ref: 'Psalm 118:6', book: 19, chapter: 118, verse: 6 },
  { ref: 'Micah 7:7', book: 33, chapter: 7, verse: 7 },
  { ref: 'Psalm 32:8', book: 19, chapter: 32, verse: 8 },
  { ref: 'John 14:27', book: 43, chapter: 14, verse: 27 },
  { ref: 'Psalm 40:1-3', book: 19, chapter: 40, verse: 1 },
  { ref: 'Isaiah 30:15', book: 23, chapter: 30, verse: 15 },
  { ref: 'Psalm 56:3, 4', book: 19, chapter: 56, verse: 3 },
  { ref: 'Habakkuk 3:19', book: 35, chapter: 3, verse: 19 },
  { ref: 'Psalm 63:7, 8', book: 19, chapter: 63, verse: 7 },
  { ref: 'Romans 12:12', book: 45, chapter: 12, verse: 12 },
  { ref: 'Psalm 86:15', book: 19, chapter: 86, verse: 15 },
  { ref: 'Isaiah 41:13', book: 23, chapter: 41, verse: 13 },
  { ref: 'Psalm 116:1, 2', book: 19, chapter: 116, verse: 1 },
  { ref: 'Philippians 4:13', book: 50, chapter: 4, verse: 13 },
  { ref: 'Psalm 119:105', book: 19, chapter: 119, verse: 105 },
  { ref: 'Isaiah 40:29', book: 23, chapter: 40, verse: 29 },
  { ref: 'Psalm 18:2', book: 19, chapter: 18, verse: 2 },
  { ref: 'Colossians 3:15', book: 51, chapter: 3, verse: 15 }];

// Extend to 365 by cycling through the base list multiple times
while (SCRIPTURES.length < 365) {
  SCRIPTURES.push(...SCRIPTURES.slice(0, 365 - SCRIPTURES.length));
}

export default async function handler(req, res) {
  try {
    const now = new Date();
    
    // Calculate day of year (1-365)
    const start = new Date(now.getFullYear(), 0, 0);
    const diff = now - start;
    const oneDay = 1000 * 60 * 60 * 24;
    const dayOfYear = Math.floor(diff / oneDay);
    
    // Pick today's scripture (0-indexed)
    const index = (dayOfYear - 1) % SCRIPTURES.length;
    const scripture = SCRIPTURES[index];
    
    // Build WOL link for this scripture
    // Format: https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/BOOK/CHAPTER#vBOOKCHAPTERVERSE
    const bookPadded = scripture.book.toString();
    const chapterPadded = scripture.chapter.toString();
    const versePadded = scripture.verse.toString().padStart(3, '0');
    const verseAnchor = `v${bookPadded.padStart(2, '0')}${chapterPadded.padStart(3, '0')}${versePadded}`;
    const wolUrl = `https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/${scripture.book}/${scripture.chapter}#${verseAnchor}`;
    
    const dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });

    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600');
    return res.status(200).json({
      reference: scripture.ref,
      wolUrl,
      dateLabel,
    });
  } catch (err) {
    console.error('Encouragement error:', err);
    return res.status(500).json({ error: err.message });
  }
}
