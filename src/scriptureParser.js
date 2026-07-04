/* --------------------------------------------------------------------------
 * scriptureParser.js
 * Extracts Bible scripture references from pasted Watchtower article text and
 * builds official Watchtower Online Library (WOL) links to the New World
 * Translation. We never store copyrighted verse text — each reference links
 * out to the official NWT on wol.jw.org (same pattern used elsewhere in the app).
 * ------------------------------------------------------------------------ */

/* Canonical book name -> list of accepted abbreviations / spellings.
 * Kept lowercase; matching is case-insensitive and ignores a trailing period. */
const BOOKS = [
  ['Genesis', ['ge', 'gen']],
  ['Exodus', ['ex', 'exo', 'exod']],
  ['Leviticus', ['le', 'lev']],
  ['Numbers', ['nu', 'num']],
  ['Deuteronomy', ['de', 'deut', 'dt']],
  ['Joshua', ['jos', 'josh']],
  ['Judges', ['jg', 'judg', 'jdg']],
  ['Ruth', ['ru', 'rth']],
  ['1 Samuel', ['1 samuel', '1samuel', '1 sam', '1sam', '1 sa', '1sa']],
  ['2 Samuel', ['2 samuel', '2samuel', '2 sam', '2sam', '2 sa', '2sa']],
  ['1 Kings', ['1 kings', '1kings', '1 kgs', '1kgs', '1 ki', '1ki']],
  ['2 Kings', ['2 kings', '2kings', '2 kgs', '2kgs', '2 ki', '2ki']],
  ['1 Chronicles', ['1 chronicles', '1 chron', '1 chr', '1chr', '1 ch', '1ch']],
  ['2 Chronicles', ['2 chronicles', '2 chron', '2 chr', '2chr', '2 ch', '2ch']],
  ['Ezra', ['ezr', 'ezra']],
  ['Nehemiah', ['ne', 'neh']],
  ['Esther', ['es', 'est', 'esth']],
  ['Job', ['job']],
  ['Psalms', ['ps', 'psa', 'psalm', 'psalms', 'psm']],
  ['Proverbs', ['pr', 'prov', 'prv']],
  ['Ecclesiastes', ['ec', 'eccl', 'eccles']],
  ['Song of Solomon', ['song of solomon', 'song of sol', 'song', 'ca']],
  ['Isaiah', ['isa', 'is']],
  ['Jeremiah', ['jer', 'je']],
  ['Lamentations', ['la', 'lam']],
  ['Ezekiel', ['eze', 'ezek', 'ezk']],
  ['Daniel', ['da', 'dan', 'dn']],
  ['Hosea', ['ho', 'hos']],
  ['Joel', ['joe', 'joel', 'jl']],
  ['Amos', ['am', 'amos']],
  ['Obadiah', ['ob', 'obad']],
  ['Jonah', ['jon', 'jnh']],
  ['Micah', ['mic', 'mc']],
  ['Nahum', ['na', 'nah']],
  ['Habakkuk', ['hab', 'hb']],
  ['Zephaniah', ['zep', 'zeph']],
  ['Haggai', ['hag', 'hg']],
  ['Zechariah', ['zec', 'zech']],
  ['Malachi', ['mal', 'ml']],
  ['Matthew', ['mt', 'matt', 'matthew']],
  ['Mark', ['mr', 'mk', 'mrk']],
  ['Luke', ['lu', 'lk', 'luke']],
  ['John', ['joh', 'jhn', 'jn', 'john']],
  ['Acts', ['ac', 'act', 'acts']],
  ['Romans', ['ro', 'rom', 'rm']],
  ['1 Corinthians', ['1 corinthians', '1 cor', '1cor', '1 co', '1co']],
  ['2 Corinthians', ['2 corinthians', '2 cor', '2cor', '2 co', '2co']],
  ['Galatians', ['ga', 'gal']],
  ['Ephesians', ['eph', 'ephes']],
  ['Philippians', ['php', 'phil', 'phi', 'philippians']],
  ['Colossians', ['col', 'cl']],
  ['1 Thessalonians', ['1 thessalonians', '1 thess', '1 thes', '1 th', '1th']],
  ['2 Thessalonians', ['2 thessalonians', '2 thess', '2 thes', '2 th', '2th']],
  ['1 Timothy', ['1 timothy', '1 tim', '1tim', '1 ti', '1ti']],
  ['2 Timothy', ['2 timothy', '2 tim', '2tim', '2 ti', '2ti']],
  ['Titus', ['tit', 'titus']],
  ['Philemon', ['phm', 'phlm', 'philem', 'philemon']],
  ['Hebrews', ['heb', 'hbr', 'hebrews']],
  ['James', ['jas', 'jam', 'jms', 'james']],
  ['1 Peter', ['1 peter', '1 pet', '1pet', '1 pe', '1pe']],
  ['2 Peter', ['2 peter', '2 pet', '2pet', '2 pe', '2pe']],
  ['1 John', ['1 john', '1john', '1 jn', '1jn', '1 jo', '1jo', '1 joh']],
  ['2 John', ['2 john', '2john', '2 jn', '2jn', '2 jo', '2jo', '2 joh']],
  ['3 John', ['3 john', '3john', '3 jn', '3jn', '3 jo', '3jo', '3 joh']],
  ['Jude', ['jude', 'jud']],
  ['Revelation', ['re', 'rev', 'revelation']],
]

/* token (lowercase, no trailing dot) -> canonical name */
const TOKEN_TO_BOOK = (() => {
  const map = new Map()
  for (const [name, abbrevs] of BOOKS) {
    map.set(name.toLowerCase(), name)
    for (const a of abbrevs) map.set(a, name)
  }
  return map
})()

/* All tokens, longest first, so "1 John" wins over "John" and "Acts" over "Ac". */
const ALL_TOKENS = Array.from(TOKEN_TO_BOOK.keys())
  .sort((a, b) => b.length - a.length)
  .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'))

/* book token, optional period, then a chapter:verse expression that may include
 * verse lists/ranges (5-8 or 7, 8) and chained chapters (36:1, 2; 37:6, 7). */
const REF_RE = new RegExp(
  '\\b(' + ALL_TOKENS.join('|') + ')\\.?\\s+' +
  '(\\d+:\\d+(?:\\s*[-–,]\\s*\\d+)*(?:\\s*;\\s*\\d+(?::\\d+)?(?:\\s*[-–,]\\s*\\d+)*)*)',
  'gi'
)

function wolUrl(fullName, chapter, verses) {
  const q = `${fullName} ${chapter}:${verses.replace(/\s+/g, '')}`
  return `https://wol.jw.org/en/wol/l/r1/lp-e?q=${encodeURIComponent(q)}`
}

/**
 * Extract every scripture reference from a block of article text.
 * @param {string} text - pasted Watchtower article
 * @returns {{ref:string,url:string,book:string,chapter:string,verses:string,isRead:boolean}[]}
 *          de-duplicated, in order of first appearance.
 */
export function extractScriptures(text) {
  if (!text || typeof text !== 'string') return []
  const seen = new Set()
  const out = []
  let m
  REF_RE.lastIndex = 0
  while ((m = REF_RE.exec(text)) !== null) {
    const token = m[1].toLowerCase().replace(/\.$/, '').replace(/\s+/g, ' ')
    const fullName = TOKEN_TO_BOOK.get(token)
    if (!fullName) continue

    // Was this reference introduced with "Read"? Those are the key texts.
    const before = text.slice(Math.max(0, m.index - 12), m.index)
    const isRead = /\bread\W*$/i.test(before)

    // A single citation can chain chapters: "36:1, 2; 37:6, 7" -> two entries.
    let currentChapter = null
    for (const rawSeg of m[2].split(';')) {
      const seg = rawSeg.trim()
      if (!seg) continue
      let chapter, verses
      if (seg.includes(':')) {
        const [c, v] = seg.split(':')
        chapter = c.trim()
        verses = v.trim()
        currentChapter = chapter
      } else {
        if (!currentChapter) continue
        chapter = currentChapter
        verses = seg
      }
      const displayVerses = verses.replace(/\s*([-–])\s*/g, '$1').replace(/\s*,\s*/g, ', ')
      const key = `${fullName} ${chapter}:${verses.replace(/\s+/g, '')}`
      if (seen.has(key)) continue
      seen.add(key)
      out.push({
        ref: `${fullName} ${chapter}:${displayVerses}`,
        url: wolUrl(fullName, chapter, verses),
        book: fullName,
        chapter,
        verses: displayVerses,
        isRead,
      })
    }
  }
  return out
}

/** Convenience: split extracted refs into "read" (key) texts and the rest. */
export function groupScriptures(refs) {
  return {
    read: refs.filter(r => r.isRead),
    related: refs.filter(r => !r.isRead),
  }
}
