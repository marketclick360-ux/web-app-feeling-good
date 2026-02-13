import https from 'https'

// Server-side cached meeting data (updated periodically)
const WEEKLY_MEETINGS = {
  '2026-02-09': {
    theme: 'He Is the Stability of Your Times',
    bibleReading: 'Isaiah 33-35',
    song: 'Song 3 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/',
    sundayArticle: 'The Book of Job Can Help You When You Give Counsel',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "He Is the Stability of Your Times" (10 min.) — Isa 33:6' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 35:8' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 35:1-10' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 60-61' }
      ]
    }
  },
  '2026-02-16': {
    theme: 'Do Not Be Afraid Because of the Words That You Heard',
    bibleReading: 'Isaiah 36-37',
    song: 'Song 150 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Do Not Be Afraid Because of the Words That You Heard" (10 min.) — Isa 36:1, 2; 37:6, 7' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 37:29' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 37:14-23' }
      ],
      living: [
        { id: 'local_needs', text: '📌 "What Is the Basis for Your Confidence?" (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 62-63' }
      ]
    }
  },
  '2026-02-23': {
    theme: 'Like a Shepherd He Will Care For His Flock',
    bibleReading: 'Isaiah 38-40',
    song: 'Song 4 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-23-March-1-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Like a Shepherd He Will Care For His Flock" (10 min.) — Isa 40:8, 11, 26-29' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 40:3' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 40:21-31' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Annual Service Report (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 64-65' }
      ]
    }
  },
  '2026-03-02': {
    theme: 'Do Not Be Afraid',
    bibleReading: 'Isaiah 41-42',
    song: 'Song 8 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-March-2-8-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Do Not Be Afraid" (10 min.) — Isa 41:10, 13' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 41:8' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 42:1-13' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Memorial Campaign (5 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 66-67' }
      ]
    }
  },
  '2026-03-09': {
    theme: 'A Prophecy Written Two Centuries in Advance',
    bibleReading: 'Isaiah 43-44',
    song: 'Song 63 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-March-9-15-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "A Prophecy Written Two Centuries in Advance" (10 min.) — Isa 44:27, 28' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 44:28' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 44:9-20' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 68-69' }
      ]
    }
  },
  '2026-03-16': {
    theme: 'I Am God, and There Is No One Like Me',
    bibleReading: 'Isaiah 45-47',
    song: 'Song 2 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-March-16-22-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "I Am God, and There Is No One Like Me" (10 min.) — Isa 46:9-11' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 46:10' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 45:1-11' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Our Only Reliable Source of Help (7 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 70-71' }
      ]
        }
  },
  '2026-03-23': {
    theme: 'Benefit From Paying Attention to Jehovah',
    bibleReading: 'Isaiah 48-49',
    song: 'Song 89 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-March-23-29-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Benefit From Paying Attention to Jehovah" (10 min.) — Isa 48:17, 18' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 49:8' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 48:9-20' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Benefit From the Most Important Day of the Year (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 72-73' }
      ]
    }
  
},
  '2026-04-06': {
    theme: 'Listen to the One Whom God Taught',
    bibleReading: 'Isaiah 50-51',
    song: 'Song 88 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-April-6-12-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Listen to the One Whom God Taught" (10 min.) — Isa 50:4' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 51:1' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 50:1-11' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 74-75' }
      ]
    }
  },
  '2026-04-13': {
    theme: 'What Love Jesus Showed!',
    bibleReading: 'Isaiah 52-53',
    song: 'Song 18 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-April-13-19-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "What Love Jesus Showed!" (10 min.) — Isa 53:3' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 52:11' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 53:3-12' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Become Jehovah’s Friend—The Greatest Act of Love (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 76-77' }
      ]
    }
  },
  '2026-04-20': {
    theme: 'How Much Are You Willing to Pay?',
    bibleReading: 'Isaiah 54-55',
    song: 'Song 86 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-April-20-26-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "How Much Are You Willing to Pay?" (10 min.) — Isa 54:13' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 54:17' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 54:1-10' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Overcoming Obstacles to Personal Study (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 78-79' }
      ]
    }
  },
  '2026-04-27': {
    theme: 'We Are Happy to Have Jehovah as Our God',
    bibleReading: 'Isaiah 56-57',
    song: 'Song 12 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/march-april-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-April-27-May-3-2026/',
    sundayArticle: '',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "We Are Happy to Have Jehovah as Our God" (10 min.) — Isa 57:13' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 56:6, 7' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 56:4-12' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Never Stop Talking About Jehovah (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 80-81' }
      ]
    }
  }
    }

const DEFAULT_WEEK = {
  theme: '', bibleReading: '', song: 'Song and Prayer',
  workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
  sundayArticle: '', sundayScriptures: [],
  sections: {
    treasures: [
      { id: 'talk', text: '🎤 Talk (10 min.)' },
      { id: 'gems', text: '🔍 Spiritual Gems (10 min.)' },
      { id: 'reading', text: '📖 Bible Reading (4 min.)' }
    ],
    living: [
      { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
      { id: 'cbs', text: '📕 Congregation Bible Study (30 min.)' }
    ]
  }
}

function fetchPage(url, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout')), timeout)
    const parsed = new URL(url)
    const options = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MeetingBot/1.0)',
        'Accept': 'text/html',
        'Accept-Language': 'en-US,en;q=0.5'
      }
    }
    https.get(options, (resp) => {
      if (resp.statusCode >= 300 && resp.statusCode < 400 && resp.headers.location) {
        clearTimeout(timer)
        fetchPage(resp.headers.location, timeout).then(resolve).catch(reject)
        return
      }
      let data = ''
      resp.on('data', chunk => data += chunk)
      resp.on('end', () => { clearTimeout(timer); resolve({ ok: resp.statusCode >= 200 && resp.statusCode < 300, status: resp.statusCode, text: data }) })
      resp.on('error', e => { clearTimeout(timer); reject(e) })
    }).on('error', e => { clearTimeout(timer); reject(e) })
  })
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  try {
    const { week } = req.query
    if (!week) return res.status(400).json({ error: 'Missing ?week=YYYY-MM-DD' })
    const mon = new Date(week + 'T12:00:00Z')
    if (isNaN(mon.getTime())) return res.status(400).json({ error: 'Invalid date' })
    
    // Check server-side cache first
    if (WEEKLY_MEETINGS[week]) {
      res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=3600')
      return res.status(200).json({ ...WEEKLY_MEETINGS[week], weekKey: week, source: 'cached' })
    }
    
    // Build workbook URL for scraping
    const sun = new Date(mon)
    sun.setDate(sun.getDate() + 6)
    const months = ['january','february','march','april','may','june','july','august','september','october','november','december']
    const monMonth = mon.getMonth()
    const monYear = mon.getFullYear()
    const sunMonth = sun.getMonth()
    const sunYear = sun.getFullYear()
    const monDay = mon.getDate()
    const sunDay = sun.getDate()
    const monName = months[monMonth]
    const sunName = months[sunMonth]
    const capMon = monName.charAt(0).toUpperCase() + monName.slice(1)
    const capSun = sunName.charAt(0).toUpperCase() + sunName.slice(1)
    const biMonthPairs = [[0,1],[0,1],[2,3],[2,3],[4,5],[4,5],[6,7],[6,7],[8,9],[8,9],[10,11],[10,11]]
    const pair = biMonthPairs[monMonth]
    const slug1 = months[pair[0]]
    const slug2 = months[pair[1]]
    const mwbSlug = `${slug1}-${slug2}-${monYear}-mwb`
    let scheduleSlug
    if (monMonth === sunMonth) {
      scheduleSlug = `Life-and-Ministry-Meeting-Schedule-for-${capMon}-${monDay}-${sunDay}-${monYear}`
    } else {
      scheduleSlug = `Life-and-Ministry-Meeting-Schedule-for-${capMon}-${monDay}-${capSun}-${sunDay}-${sunYear}`
    }
    const workbookUrl = `https://www.jw.org/en/library/jw-meeting-workbook/${mwbSlug}/${scheduleSlug}/`
    
    // Return default with correct workbook URL when not cached
    const result = { ...DEFAULT_WEEK, weekKey: week, workbookUrl, source: 'fallback' }
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600')
    return res.status(200).json(result)
  } catch (err) {
    console.error('Meeting data error:', err)
    return res.status(500).json({ error: err.message })
  }
}
