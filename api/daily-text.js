export default async function handler(req, res) {
  try {
    const now = new Date()
    const url = `https://wol.jw.org/wol/dt/r1/lp-e/${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}`
    const r = await fetch(url)
    if (!r.ok) throw new Error('Failed to fetch daily text')
    const data = await r.json()
    const item = data.items && data.items[0]
    if (!item || !item.content) {
      return res.status(404).json({ error: 'No daily text found' })
    }
    // Extract scripture theme from <em> tag
    const emMatch = item.content.match(/<em>(.*?)<\/em>/s)
    const scripture = emMatch ? emMatch[1].replace(/<[^>]+>/g, '').trim() : ''
    // Extract the theme scripture reference (e.g. "Gen. 3:6")
    const refMatch = item.content.match(/<em>.*?<\/em>(.*?)<\/p>/s)
    const reference = refMatch ? refMatch[1].replace(/<[^>]+>/g, '').replace(/^[\s\u2014\-]+/, '').trim() : ''
    // Get comment paragraphs from bodyTxt div
    const bodyStart = item.content.indexOf('bodyTxt')
    let comment = ''
    if (bodyStart > -1) {
            const bodyHtml = item.content.slice(item.content.indexOf('>', bodyStart) + 1)
      comment = bodyHtml
        .replace(/<a[^>]*>[\s\S]*?<\/a>/g, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    }
    const dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    })
      const wolUrl = 'https://wol.jw.org/en/wol/dt/r1/lp-e'
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600')
    return res.status(200).json({ scripture, reference, comment, dateLabel, wolUrl })
  } catch (err) {
    console.error('Daily text error:', err)
    return res.status(500).json({ error: err.message })
  }
}