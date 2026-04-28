export default async function handler(req, res) {
  try {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const day = now.getDate();

    const wolUrl = `https://wol.jw.org/en/wol/dt/r1/lp-e/${year}/${month}/${day}`;

    const dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });

    let scripture = '';
    let reference = '';
    let comment = '';

    try {
      const ctrl = new AbortController();
      const timeout = setTimeout(() => ctrl.abort(), 8000);

      const response = await fetch(wolUrl, {
        signal: ctrl.signal,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9',
          'Cache-Control': 'no-cache',
        },
      });
      clearTimeout(timeout);

      if (response.ok) {
        const html = await response.text();
        const extracted = parseWolHtml(html);
        scripture = extracted.scripture;
        reference = extracted.reference;
        comment = extracted.comment;
      }
    } catch (fetchErr) {
      console.warn('Daily text fetch failed:', fetchErr.message);
    }

    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600');

    return res.status(200).json({
      dateLabel,
      wolUrl,
      scripture,
      reference,
      comment,
      note: '',
    });
  } catch (err) {
    console.error('Daily text error:', err);
    return res.status(500).json({ error: err.message });
  }
}

function parseWolHtml(html) {
  let scripture = '';
  let reference = '';
  let comment = '';

  // Reference — lives in <p class="themeScrp"> with a nested link
  const refPatterns = [
    /class="themeScrp[^"]*"[^>]*>[\s\S]*?<a[^>]*>([^<]+)<\/a>/,
    /class="themeScrp[^"]*"[^>]*>([^<\n]{3,80})</,
  ];
  for (const pat of refPatterns) {
    const m = html.match(pat);
    if (m?.[1]?.trim()) { reference = m[1].trim(); break; }
  }

  // Verse text — lives in a <blockquote> or element with class containing "scrp"
  const versePatterns = [
    /<blockquote[^>]*>([\s\S]*?)<\/blockquote>/i,
    /class="[^"]*scrp[^"]*"[^>]*>([\s\S]*?)<\/(?:p|div|span)>/i,
  ];
  for (const pat of versePatterns) {
    const m = html.match(pat);
    if (m?.[1]) {
      const text = m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
      if (text.length > 15) { scripture = text; break; }
    }
  }

  // Comment — body paragraphs with class "sb" (WOL's standard body class)
  // Pull from the article body; skip the first paragraph (theme scripture)
  const articleMatch = html.match(/<article[^>]*>([\s\S]*?)<\/article>/i)
    || html.match(/class="[^"]*bodyTxt[^"]*"[^>]*>([\s\S]{100,})/i);

  if (articleMatch) {
    const body = articleMatch[1];
    const paragraphs = [];
    const pRegex = /<p[^>]*class="[^"]*\bsb\b[^"]*"[^>]*>([\s\S]*?)<\/p>/gi;
    let m;
    let count = 0;
    while ((m = pRegex.exec(body)) !== null) {
      if (count++ === 0) continue; // first sb paragraph is the theme scripture
      const text = m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
      if (text.length > 15) paragraphs.push(text);
    }
    comment = paragraphs.join(' ');
  }

  return { scripture, reference, comment };
}
