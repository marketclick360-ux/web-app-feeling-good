export default async function handler(req, res) {
  try {
    const now = new Date();

    // Build today's official WOL daily text URL
    const wolUrl = `https://wol.jw.org/en/wol/dt/r1/lp-e/${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}`;

    const dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });

    // Optional: your own short note (leave '' if you don't want one)
    const note = '';

    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600');

    return res.status(200).json({
      dateLabel,  // e.g. "Wednesday, February 11, 2026"
      wolUrl,     // link to today's daily text on wol.jw.org
      note,       // your own comment, NOT copied text
    });
  } catch (err) {
    console.error('Daily text error:', err);
    return res.status(500).json({ error: err.message });
  }
}
