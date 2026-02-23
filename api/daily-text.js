export default async function handler(req, res) {
  try {
    const now = new Date();

    // Use Texas timezone for consistent date
    const texasFormatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Chicago',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric'
    });
    const parts = texasFormatter.formatToParts(now);
    const year = Number(parts.find(p => p.type === 'year').value);
    const month = Number(parts.find(p => p.type === 'month').value);
    const day = Number(parts.find(p => p.type === 'day').value);

    // Build today's official WOL daily text URL
    const wolUrl = `https://wol.jw.org/en/wol/dt/r1/lp-e/${year}/${month}/${day}`;

    const dateLabel = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Chicago',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    }).format(now);

    // Try to scrape the daily text from WOL
    let scripture = '';
    let reference = '';
    let comment = '';

    try {
      const response = await fetch(wolUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; DailyTextApp/1.0)',
          'Accept': 'text/html',
        },
        signal: AbortSignal.timeout(8000),
      });

      if (response.ok) {
        const html = await response.text();

        // Extract the theme scripture (paragraph #p69)
        // Pattern: <p id="p69" ...>...</p>
        const themeMatch = html.match(/<p[^>]*id="p69"[^>]*>(.*?)<\/p>/s);
        if (themeMatch) {
          // Clean HTML tags to get plain text
          let themeText = themeMatch[1]
            .replace(/<a[^>]*>(.*?)<\/a>/g, '$1') // keep link text
            .replace(/<em>(.*?)<\/em>/g, '$1')     // keep italic text
            .replace(/<[^>]+>/g, '')                // strip remaining tags
            .replace(/&nbsp;/g, ' ')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&#x2014;/g, '\u2014')
            .replace(/\u200b/g, '')                 // remove zero-width spaces
            .trim();

          // Split on the em dash to get scripture and reference
          const dashIdx = themeText.lastIndexOf('\u2014');
          if (dashIdx > 0) {
            scripture = themeText.substring(0, dashIdx).trim();
            reference = themeText.substring(dashIdx + 1).trim().replace(/\.$/, '');
          } else {
            scripture = themeText;
          }
        }

        // Extract the comment paragraph (#p70)
        const commentMatch = html.match(/<p[^>]*id="p70"[^>]*>(.*?)<\/p>/s);
        if (commentMatch) {
          comment = commentMatch[1]
            .replace(/<a[^>]*>(.*?)<\/a>/g, '$1')
            .replace(/<em>(.*?)<\/em>/g, '$1')
            .replace(/<[^>]+>/g, '')
            .replace(/&nbsp;/g, ' ')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&#x2014;/g, '\u2014')
            .replace(/\u200b/g, '')
            .trim();

          // Limit comment length for the app display
          if (comment.length > 500) {
            comment = comment.substring(0, 497) + '...';
          }
        }
      }
    } catch (scrapeErr) {
      console.error('Daily text scrape failed:', scrapeErr.message);
      // Continue with empty values - app will show fallback
    }

    // Cache for 4 hours, revalidate after 2 hours
    res.setHeader('Cache-Control', 's-maxage=14400, stale-while-revalidate=7200');

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
