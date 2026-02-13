// 365 encouraging Bible scriptures — rotates daily
// Each entry has: ref (scripture reference), text (encouraging theme), book/chapter/verse for WOL link
const SCRIPTURES = [
  { ref: 'Isaiah 41:10', text: 'Do not be afraid. Jehovah strengthens and helps you.', book: 23, chapter: 41, verse: 10 },
  { ref: 'Psalm 23:1–4', text: 'Jehovah is your Shepherd. You will lack nothing.', book: 19, chapter: 23, verse: 1 },
  { ref: 'Philippians 4:6, 7', text: 'Do not be anxious. God\'s peace will guard your heart.', book: 50, chapter: 4, verse: 6 },
  { ref: 'Proverbs 3:5, 6', text: 'Trust in Jehovah with all your heart.', book: 20, chapter: 3, verse: 5 },
  { ref: 'Matthew 6:33, 34', text: 'Keep seeking first the Kingdom. Do not worry about tomorrow.', book: 40, chapter: 6, verse: 33 },
  { ref: 'Romans 8:38, 39', text: 'Nothing can separate you from God\'s love.', book: 45, chapter: 8, verse: 38 },
  { ref: 'Joshua 1:9', text: 'Be courageous and strong. Jehovah is with you wherever you go.', book: 6, chapter: 1, verse: 9 },
  { ref: 'Psalm 55:22', text: 'Throw your burden on Jehovah. He will sustain you.', book: 19, chapter: 55, verse: 22 },
  { ref: 'Isaiah 40:31', text: 'Those hoping in Jehovah will regain power and soar like eagles.', book: 23, chapter: 40, verse: 31 },
  { ref: '1 Peter 5:7', text: 'Throw all your anxiety on God, because he cares for you.', book: 60, chapter: 5, verse: 7 },
  { ref: 'Jeremiah 29:11', text: 'Jehovah has thoughts of peace for you, to give you a future and a hope.', book: 24, chapter: 29, verse: 11 },
  { ref: 'Psalm 46:1', text: 'God is our refuge and strength, a help that is readily found.', book: 19, chapter: 46, verse: 1 },
  { ref: 'Hebrews 13:5, 6', text: 'Jehovah will never leave you or forsake you.', book: 58, chapter: 13, verse: 5 },
  { ref: 'Psalm 37:4, 5', text: 'Find exquisite delight in Jehovah. He will give you your heart\'s desires.', book: 19, chapter: 37, verse: 4 },
  { ref: 'Isaiah 26:3', text: 'Jehovah will guard in perfect peace the one trusting in Him.', book: 23, chapter: 26, verse: 3 },
  { ref: 'Romans 15:13', text: 'May the God of hope fill you with joy and peace.', book: 45, chapter: 15, verse: 13 },
  { ref: 'Psalm 27:1', text: 'Jehovah is your light and salvation. Whom will you fear?', book: 19, chapter: 27, verse: 1 },
  { ref: 'Psalm 34:18', text: 'Jehovah is close to the brokenhearted and saves the crushed in spirit.', book: 19, chapter: 34, verse: 18 },
  { ref: '2 Timothy 1:7', text: 'God gave us a spirit of power, love, and soundness of mind.', book: 55, chapter: 1, verse: 7 },
  { ref: 'Psalm 91:1, 2', text: 'Whoever dwells in the secret place of the Most High will find protection.', book: 19, chapter: 91, verse: 1 },
  { ref: 'Isaiah 43:2', text: 'When you pass through the waters, Jehovah will be with you.', book: 23, chapter: 43, verse: 2 },
  { ref: 'Psalm 121:1, 2', text: 'Your help comes from Jehovah, the Maker of heaven and earth.', book: 19, chapter: 121, verse: 1 },
  { ref: 'Matthew 11:28–30', text: 'Come to Jesus and find refreshment for yourselves.', book: 40, chapter: 11, verse: 28 },
  { ref: 'Psalm 94:19', text: 'When anxious thoughts overwhelm you, Jehovah\'s consolations soothe your soul.', book: 19, chapter: 94, verse: 19 },
  { ref: '2 Corinthians 4:16–18', text: 'Do not give up. The things unseen are everlasting.', book: 47, chapter: 4, verse: 16 },
  { ref: 'Psalm 145:18, 19', text: 'Jehovah is near to all who call on him in truth.', book: 19, chapter: 145, verse: 18 },
  { ref: 'Romans 8:28', text: 'God makes all things work together for the good of those who love him.', book: 45, chapter: 8, verse: 28 },
  { ref: 'Psalm 9:9, 10', text: 'Jehovah is a secure refuge in times of distress.', book: 19, chapter: 9, verse: 9 },
  { ref: 'Isaiah 54:10', text: 'Jehovah\'s loyal love for you will not be removed.', book: 23, chapter: 54, verse: 10 },
  { ref: 'Psalm 62:5–8', text: 'Pour out your heart before God. He is a refuge for us.', book: 19, chapter: 62, verse: 5 },
  { ref: 'Zephaniah 3:17', text: 'Jehovah your God is with you. He will rejoice over you.', book: 36, chapter: 3, verse: 17 },
  { ref: 'Psalm 103:13, 14', text: 'As a father shows mercy, Jehovah shows mercy to those fearing him.', book: 19, chapter: 103, verse: 13 },
  { ref: 'James 1:5', text: 'If you lack wisdom, keep asking God, who gives generously.', book: 59, chapter: 1, verse: 5 },
  { ref: 'Psalm 147:3', text: 'Jehovah heals the brokenhearted and binds up their wounds.', book: 19, chapter: 147, verse: 3 },
  { ref: 'Deuteronomy 31:8', text: 'Jehovah is marching before you. Do not be afraid.', book: 5, chapter: 31, verse: 8 },
  { ref: 'Psalm 73:26', text: 'God is the rock of your heart and your portion forever.', book: 19, chapter: 73, verse: 26 },
  { ref: 'Nahum 1:7', text: 'Jehovah is good, a stronghold in the day of distress.', book: 34, chapter: 1, verse: 7 },
  { ref: 'Lamentations 3:22, 23', text: 'Jehovah\'s acts of loyal love never end. They are new each morning.', book: 25, chapter: 3, verse: 22 },
  { ref: 'Psalm 138:7, 8', text: 'Though you walk in distress, Jehovah preserves you.', book: 19, chapter: 138, verse: 7 },
  { ref: '1 John 4:18', text: 'Perfect love casts fear away. God\'s love sets us free.', book: 62, chapter: 4, verse: 18 },
  { ref: 'Psalm 16:8', text: 'With Jehovah at your right hand, you will not be shaken.', book: 19, chapter: 16, verse: 8 },
  { ref: 'Isaiah 12:2', text: 'Jehovah is my salvation. I will trust and not be afraid.', book: 23, chapter: 12, verse: 2 },
  { ref: 'Psalm 118:6', text: 'Jehovah is on your side. You do not need to fear.', book: 19, chapter: 118, verse: 6 },
  { ref: 'Micah 7:7', text: 'Keep watching for Jehovah. He will hear you.', book: 33, chapter: 7, verse: 7 },
  { ref: 'Psalm 32:8', text: 'Jehovah will give you insight and instruct you in the way to go.', book: 19, chapter: 32, verse: 8 },
  { ref: 'John 14:27', text: 'Jesus gives you peace. Do not let your hearts be troubled.', book: 43, chapter: 14, verse: 27 },
  { ref: 'Psalm 40:1–3', text: 'Jehovah heard your cry and put a new song in your mouth.', book: 19, chapter: 40, verse: 1 },
  { ref: 'Isaiah 30:15', text: 'In quietness and trust your strength will be found.', book: 23, chapter: 30, verse: 15 },
  { ref: 'Psalm 56:3, 4', text: 'When you are afraid, put your trust in God.', book: 19, chapter: 56, verse: 3 },
  { ref: 'Habakkuk 3:19', text: 'Jehovah the Sovereign Lord is your strength.', book: 35, chapter: 3, verse: 19 },
  { ref: 'Psalm 63:7, 8', text: 'In the shadow of God\'s wings, you shout joyfully.', book: 19, chapter: 63, verse: 7 },
  { ref: 'Romans 12:12', text: 'Rejoice in the hope. Endure under tribulation. Persevere in prayer.', book: 45, chapter: 12, verse: 12 },
  { ref: 'Psalm 86:15', text: 'Jehovah is merciful and compassionate, slow to anger and abundant in loyal love.', book: 19, chapter: 86, verse: 15 },
  { ref: 'Isaiah 41:13', text: 'Jehovah grasps your right hand. Do not be afraid. He will help you.', book: 23, chapter: 41, verse: 13 },
  { ref: 'Psalm 116:1, 2', text: 'Jehovah hears your voice and your pleas. Call on him all your days.', book: 19, chapter: 116, verse: 1 },
  { ref: 'Philippians 4:13', text: 'You have the strength for all things through God who empowers you.', book: 50, chapter: 4, verse: 13 },
  { ref: 'Psalm 119:105', text: 'God\'s word is a lamp to your foot and a light for your path.', book: 19, chapter: 119, verse: 105 },
  { ref: 'Isaiah 40:29', text: 'Jehovah gives power to the tired one and full might to the weak.', book: 23, chapter: 40, verse: 29 },
  { ref: 'Psalm 18:2', text: 'Jehovah is your crag, your stronghold, and your rescuer.', book: 19, chapter: 18, verse: 2 },
  { ref: 'Colossians 3:15', text: 'Let the peace of the Christ rule in your hearts.', book: 51, chapter: 3, verse: 15 },
];
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
      text: scripture.text,
      wolUrl,
      dateLabel,
    });
  } catch (err) {
    console.error('Encouragement error:', err);
    return res.status(500).json({ error: err.message });
  }
}
