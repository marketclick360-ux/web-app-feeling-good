import https from 'https'
// Server-side cached meeting data (updated periodically)
const WEEKLY_MEETINGS = {
    '2025-12-29': {
    theme: 'Enemies of God\'s People Do Not Escape Punishment',
    bibleReading: 'Isaiah 14-16',
    song: 'Song 63 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/november-december-2025-mwb/Life-and-Ministry-Meeting-Schedule-for-December-29-2025-January-4-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-october-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Enemies of God\'s People Do Not Escape Punishment" (10 min.) — Isa 14:13-15, 22, 23' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 14:1, 2' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 16:1-14' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 48-49' }
      ]
    }
  },
  '2026-01-05': {
    theme: 'The Share of Those Pillaging Us',
    bibleReading: 'Isaiah 17-20',
    song: 'Song 153 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-5-11-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-november-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "The Share of Those Pillaging Us" (10 min.) — Isa 17:12-14' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 20:2' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 19:1-12' }
      ],
      living: [
        { id: 'local_needs', text: '📌 "Remember the Rock of Your Fortress" (10 min.)' },
        { id: 'talk2', text: '📌 Make Time Every Day to Learn From Jehovah\'s Friends (5 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 50-51' }
      ]
    }
  },
  '2026-01-12': {
    theme: 'Lessons From Shebna\'s Downfall',
    bibleReading: 'Isaiah 21-23',
    song: 'Song 120 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-12-18-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-november-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Lessons From Shebna\'s Downfall" (10 min.) — Isa 22:15-19' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 21:1' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 23:1-14' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 52-53' }
      ]
    }
  },
  '2026-01-19': {
    theme: 'This Is Our God!',
    bibleReading: 'Isaiah 24-27',
    song: 'Song 159 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-19-25-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-november-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "This Is Our God!" (10 min.) — Isa 25:6-9' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 24:2' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 25:1-9' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Fully Lean On Jehovah When Preparing for Medical or Surgical Care (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 54-55' }
      ]
    }
  },
  '2026-01-26': {
    theme: 'Honor Jehovah With Your Lips and Your Heart',
    bibleReading: 'Isaiah 28-29',
    song: 'Song 28 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-January-26-February-1-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-november-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Honor Jehovah With Your Lips and Your Heart" (10 min.) — Isa 29:13' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 29:1' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 29:13-24' }
      ],
      living: [
        { id: 'local_needs', text: '📌 "I Always Do the Things Pleasing to Him" (8 min.)' },
        { id: 'local_needs2', text: '📌 Local Needs (7 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 56-57' }
      ]
    }
  },
  '2026-02-02': {
    theme: 'Find Refuge Under Jehovah\'s Wings',
    bibleReading: 'Isaiah 30-32',
    song: 'Song 8 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-2-8-2026/',
    sundayArticle: '',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-december-2025/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "Find Refuge Under Jehovah\'s Wings" (10 min.) — Isa 31:5; 32:1, 2, 16-18' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 30:20' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 31:1-9' }
      ],
      living: [
        { id: 'local_needs', text: '📌 "The Result of True Righteousness Will Be Peace" (15 min.)' },
        { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 58-59' }
      ]
    }
  },
'2026-02-09': {
    theme: 'He Is the Stability of Your Times',
    bibleReading: 'Isaiah 33-35',
    song: 'Song 3 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/',
    sundayArticle: 'The Book of Job Can Help You When You Give Counsel',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-december-2025/The-Book-of-Job-Can-Help-You-When-You-Give-Counsel/',
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
        sundayArticle: 'Imitate Jehovah\'s Humility',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-december-2025/Imitate-Jehovahs-Humility/',
        sundayScriptures: [
      { ref: 'Ephesians 5:1', url: 'https://www.jw.org/en/library/bible/study-bible/books/ephesians/5/#v49005001' },
      { ref: 'Psalm 113:5-8', url: 'https://www.jw.org/en/library/bible/study-bible/books/psalms/113/#v19113005-v19113008' },
      { ref: 'Psalm 62:8', url: 'https://www.jw.org/en/library/bible/study-bible/books/psalms/62/#v19062008' },
      { ref: 'Psalm 138:6', url: 'https://www.jw.org/en/library/bible/study-bible/books/psalms/138/#v19138006' },
      { ref: '2 Peter 3:9', url: 'https://www.jw.org/en/library/bible/study-bible/books/2-peter/3/#v61003009' }
    ],
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
        sundayArticle: 'How to Plan a Wedding That Brings Honor to Jehovah',
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-december-2025/How-to-Plan-a-Wedding-That-Brings-Honor-to-Jehovah/',
        sundayScriptures: [
      { ref: '1 Corinthians 14:40', url: 'https://www.jw.org/en/library/bible/study-bible/books/1-corinthians/14/#v46014040' },
      { ref: '1 Corinthians 10:31, 32', url: 'https://www.jw.org/en/library/bible/study-bible/books/1-corinthians/10/#v46010031-v46010032' },
      { ref: 'Romans 13:13', url: 'https://www.jw.org/en/library/bible/study-bible/books/romans/13/#v45013013' },
      { ref: '1 John 2:15-17', url: 'https://www.jw.org/en/library/bible/study-bible/books/1-john/2/#v62002015-v62002017' },
      { ref: 'Philippians 4:6, 7', url: 'https://www.jw.org/en/library/bible/study-bible/books/philippians/4/#v50004006-v50004007' }
    ],
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-january-2026/Continue-to-Satisfy-Your-Spiritual-Need/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-january-2026/You-Can-Successfully-Fight-Negative-Feelings/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-january-2026/Why-We-Need-the-Ransom/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-january-2026/How-Will-You-Respond-to-the-Ransom/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-february-2026/How-to-Help-Our-Unbelieving-Relatives/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-february-2026/Understanding-the-Meaning-of-Baptism/',
    sundayScriptures: [],
    sections: {
      treasures: [
        { id: 'talk', text: '🎤 Talk: "What Love Jesus Showed!" (10 min.) — Isa 53:3' },
        { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 52:11' },
        { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 53:3-12' }
      ],
      living: [
        { id: 'local_needs', text: '📌 Become Jehovah\'s Friend—The Greatest Act of Love (15 min.)' },
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-february-2026/Keep-Working-Toward-Baptism/',
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
    sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-february-2026/Are-You-Prepared-for-Challenges-After-Baptism/',
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
  },
    '2026-05-04': {
        theme: 'Fully Experience Jehovah\'s Blessing',
        bibleReading: 'Isaiah 58-59',
        song: 'Song 21 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-May-4-10-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-march-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "Fully Experience Jehovah\'s Blessing" (10 min.) — Isa 58:7-9, 13, 14; 59:1' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 59:11' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 59:1-12' }
            ],
            living: [
                { id: 'local_needs', text: '📌 "Follow the Course of Hospitality" (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 82-83' }
            ]
        }
    },
    '2026-05-11': {
        theme: '"Arise, O Woman, Shed Light"',
        bibleReading: 'Isaiah 60-61',
        song: 'Song 146 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-May-11-17-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-march-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "Arise, O Woman, Shed Light" (10 min.) — Isa 60:1, 2' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 61:1' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 61:1-9' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 84-85' }
            ]
        }
    },
    '2026-05-18': {
        theme: 'The Loving and Compassionate Potter',
        bibleReading: 'Isaiah 62-64',
        song: 'Song 44 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-May-18-24-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-march-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "The Loving and Compassionate Potter" (10 min.) — Isa 63:9; 64:8' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 63:10' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 64:4-12' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Disaster Preparedness—Expect the Unexpected (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 86-87' }
            ]
        }
    },
    '2026-05-25': {
        theme: 'We Love Our Spiritual Paradise!',
        bibleReading: 'Isaiah 65-66',
        song: 'Song 24 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-May-25-31-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-march-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "We Love Our Spiritual Paradise!" (10 min.) — Isa 65:13, 14-17, 25' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Isa 66:24' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Isaiah 65:17-25' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Are You Missing Out? (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 88-89' }
            ]
        }
    },
    '2026-06-01': {
        theme: 'Do Not Be Afraid . . . for "I Am With You"',
        bibleReading: 'Jeremiah 1-3',
        song: 'Song 84 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-June-1-7-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-april-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "Do Not Be Afraid . . . for I Am With You" (10 min.) — Jer 1:6, 8, 9' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Jer 2:28' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Jeremiah 3:14-25' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Be Bold Like Jeremiah (6 min.)' },
                { id: 'talk2', text: '📌 "Make a Defense . . . With a Mild Temper and Deep Respect" (9 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 90-91' }
            ]
        }
    },
    '2026-06-08': {
        theme: 'Learn From Judah\'s Spiritual Sickness',
        bibleReading: 'Jeremiah 4-6',
        song: 'Song 56 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-June-8-14-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-april-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "Learn From Judah\'s Spiritual Sickness" (10 min.) — Jer 4:4, 14; 5:31; 6:17-19' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Jer 4:10' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Jeremiah 5:1-11' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Protect Your Heart From Misinformation (8 min.)' },
                { id: 'local_needs2', text: '📌 Local Needs (7 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 92-93' }
            ]
        }
    },
    '2026-06-15': {
        theme: 'They Treated Jehovah\'s Temple With Contempt',
        bibleReading: 'Jeremiah 7-8',
        song: 'Song 152 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-June-15-21-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-april-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "They Treated Jehovah\'s Temple With Contempt" (10 min.) — Jer 7:4, 8-14' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Jer 8:22' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Jeremiah 8:4-13' }
            ],
            living: [
                { id: 'local_needs', text: '📌 How We Can Show Appreciation for Our Kingdom Halls (5 min.)' },
                { id: 'talk2', text: '📌 How Your Donations Are Used—Maintaining Our Kingdom Halls (10 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 94-95' }
            ]
        }
    },
    '2026-06-22': {
        theme: 'What Will You Boast About?',
        bibleReading: 'Jeremiah 9-10',
        song: 'Song 5 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-June-22-28-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-april-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "What Will You Boast About?" (10 min.) — Jer 9:23, 24' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Jer 10:21' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Jeremiah 9:13-24' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Avoid Deception, and Follow the Kingdom (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 96-97' }
            ]
        }
    },
    '2026-06-29': {
        theme: 'How to "Run a Race Against Horses"',
        bibleReading: 'Jeremiah 11-12',
        song: 'Song 106 and Prayer',
        workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/may-june-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-June-29-July-5-2026/',
        sundayArticle: '',
        sundayArticleUrl: 'https://www.jw.org/en/library/magazines/watchtower-study-april-2026/',
        sundayScriptures: [],
        sections: {
            treasures: [
                { id: 'talk', text: '🎤 Talk: "How to Run a Race Against Horses" (10 min.) — Jer 11:21; 12:5' },
                { id: 'gems', text: '🔍 Spiritual Gems (10 min.) — Jer 12:1, 3' },
                { id: 'reading', text: '📖 Bible Reading (4 min.) — Jeremiah 12:1-11' }
            ],
            living: [
                { id: 'local_needs', text: '📌 Local Needs (15 min.)' },
                { id: 'cbs', text: '📕 Congregation Bible Study (30 min.) — lfb lessons 98-99' }
            ]
        }
    }
}

const DEFAULT_WEEK = {
  theme: '', bibleReading: '', song: 'Song and Prayer',
  workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
  sundayArticle: '', sundayArticleUrl: '', sundayScriptures: [],
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

    // Build dynamic Watchtower Study Edition URL (issue is ~2 months before study week)
    const wtDate = new Date(mon)
    wtDate.setMonth(wtDate.getMonth() - 2)
    const wtMonth = months[wtDate.getMonth()]
    const wtYear = wtDate.getFullYear()
    const sundayArticleUrl = `https://www.jw.org/en/library/magazines/watchtower-study-${wtMonth}-${wtYear}/`
    
    // Return default with correct workbook URL and WT edition URL when not cached
    const result = { ...DEFAULT_WEEK, weekKey: week, workbookUrl, sundayArticleUrl, source: 'fallback' }
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600')
    return res.status(200).json(result)
  } catch (err) {
    console.error('Meeting data error:', err)
    return res.status(500).json({ error: err.message })
  }
}
