import https from 'https'

function fetchPage(url) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
      }
    }
    https.get(url, options, (resp) => {
      if (resp.statusCode >= 300 && resp.statusCode < 400 && resp.headers.location) {
        fetchPage(resp.headers.location).then(resolve).catch(reject)
        return
      }
      let data = ''
      resp.on('data', chunk => data += chunk)
      resp.on('end', () => resolve({ ok: resp.statusCode >= 200 && resp.statusCode < 300, status: resp.statusCode, text: data }))
      resp.on('error', reject)
    }).on('error', reject)
  })
}

export default async function handler(req, res) {
  try {
    const { week } = req.query
    if (!week) {
      return res.status(400).json({ error: 'Missing ?week=YYYY-MM-DD parameter' })
    }
    const mon = new Date(week + 'T12:00:00Z')
    if (isNaN(mon.getTime())) {
      return res.status(400).json({ error: 'Invalid date format. Use YYYY-MM-DD (Monday).' })
    }
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
    const fallback = {
      weekKey: week,
      theme: '',
      bibleReading: '',
      song: 'Song and Prayer',
      workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
      sundayArticle: '',
      sundayScriptures: [],
      sections: {
        treasures: [
          { id: 'talk', text: '\ud83c\udfa4 Talk (10 min.)' },
          { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.)' },
          { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.)' }
        ],
        living: [
          { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
          { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.)' }
        ]
      },
      source: 'fallback'
    }
    let pageResult
    try {
      pageResult = await fetchPage(workbookUrl)
    } catch (fetchErr) {
      console.error('Fetch error:', fetchErr.message)
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600')
      return res.status(200).json(fallback)
    }
    if (!pageResult.ok) {
      res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600')
      return res.status(200).json(fallback)
    }
    const html = pageResult.text
    const bibleRef = html.match(/<a[^>]*>([A-Z][A-Z\s]+\d+[\-\d]*)<\/a>/i)
    let bibleReadingText = ''
    if (bibleRef) {
      bibleReadingText = bibleRef[1].replace(/<[^>]+>/g, '').trim()
    }
    let song = 'Song and Prayer'
    const songMatch = html.match(/Song\s+(\d+)/i)
    if (songMatch) {
      song = `Song ${songMatch[1]} and Prayer`
    }
    let theme = ''
    const themeMatch = html.match(/\u201c([\s\S]*?)\u201d/)
    if (themeMatch) {
      theme = themeMatch[1].replace(/<[^>]+>/g, '').trim()
    }
    const treasures = []
    const talkMatch = html.match(/<h\d[^>]*>\s*1\.\s*([\s\S]*?)<\/h\d>/i)
    if (talkMatch) {
      let talkText = talkMatch[1].replace(/<[^>]+>/g, '').trim()
      treasures.push({ id: 'talk', text: '\ud83c\udfa4 Talk: \u201c' + (theme || talkText) + '\u201d (10 min.)' })
    } else {
      treasures.push({ id: 'talk', text: '\ud83c\udfa4 Talk (10 min.)' })
    }
    const gemsMatch = html.match(/<h\d[^>]*>\s*2\.\s*Spiritual\s+Gems[\s\S]*?<\/h\d>/i)
    if (gemsMatch) {
      let gemsText = gemsMatch[0].replace(/<[^>]+>/g, '').trim()
      const idx = gemsText.indexOf('Spiritual')
      treasures.push({ id: 'gems', text: '\ud83d\udd0d ' + (idx >= 0 ? gemsText.substring(idx) : 'Spiritual Gems (10 min.)') })
    } else {
      treasures.push({ id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.)' })
    }
    const readingMatch = html.match(/<h\d[^>]*>\s*3\.\s*Bible\s+Reading[\s\S]*?<\/h\d>/i)
    if (readingMatch) {
      let readText = readingMatch[0].replace(/<[^>]+>/g, '').trim()
      const idx = readText.indexOf('Bible Reading')
      treasures.push({ id: 'reading', text: '\ud83d\udcd6 ' + (idx >= 0 ? readText.substring(idx) : 'Bible Reading (4 min.)') })
    } else {
      treasures.push({ id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.)' })
    }
    const living = []
    const localMatch = html.match(/Local\s+Needs[\s\S]*?\((\d+)\s*min\.\)/i)
    if (localMatch) {
      living.push({ id: 'local_needs', text: '\ud83d\udccc Local Needs (' + localMatch[1] + ' min.)' })
    } else {
      living.push({ id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' })
    }
    const cbsMatch = html.match(/Congregation\s+Bible\s+Study[\s\S]*?\((\d+)\s*min\.\)[\s\S]*?<em>([\s\S]*?)<\/em>/i)
    if (cbsMatch) {
      let cbsRef = cbsMatch[2].replace(/<[^>]+>/g, '').trim()
      living.push({ id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (' + cbsMatch[1] + ' min.) \u2014 ' + cbsRef })
    } else {
      living.push({ id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.)' })
    }
    res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=3600')
    return res.status(200).json({
      weekKey: week,
      theme,
      bibleReading: bibleReadingText,
      song,
      workbookUrl,
      sundayArticle: '',
      sundayScriptures: [],
      sections: { treasures, living },
      source: 'scraped'
    })
  } catch (err) {
    console.error('Meeting data error:', err)
    return res.status(500).json({ error: err.message })
  }
}
