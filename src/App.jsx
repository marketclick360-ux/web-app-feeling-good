import { useState, useEffect, useCallback } from 'react'
import { supabase } from './supabaseClient'

/* --------- helpers --------- */
function mondayOf(date) {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff)
  d.setHours(0, 0, 0, 0)
  return d
}

function formatRange(mon) {
  const sun = new Date(mon)
  sun.setDate(sun.getDate() + 6)
  const opts = { month: 'long', day: 'numeric' }
  const y = mon.getFullYear()
  return `${mon.toLocaleDateString('en-US', opts)} \u2013 ${sun.toLocaleDateString('en-US', opts)}, ${y}`
}

function toISO(d) { return d.toISOString().slice(0, 10) }
function todayStr() { return toISO(new Date()) }

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good Morning'
  if (hour < 17) return 'Good Afternoon'
  return 'Good Evening'
}

const MORNING_ROUTINE = [
  { key: 'prayer_morning', label: '\ud83d\ude4f Morning prayer' },
  { key: 'daily_text', label: '\ud83d\udcc3 Read daily text' },
  { key: 'bible_reading', label: '\ud83d\udcd6 Personal Bible reading' },
  { key: 'meditation', label: '\ud83e\uddd8 Meditate on a scripture' },
  { key: 'review_goals', label: '\ud83c\udfaf Review pioneer goals for the day' },
  { key: 'prepare_service', label: '\ud83d\udcbc Prepare for field service' }
]

const EVENING_ROUTINE = [
  { key: 'review_day', label: '\ud83d\udcdd Review the day in service' },
  { key: 'study_wt', label: '\ud83d\udcd5 Study Watchtower or publication' },
  { key: 'meeting_prep', label: '\ud83d\udcda Meeting preparation' },
  { key: 'prayer_evening', label: '\ud83d\ude4f Evening prayer of thanks' },
  { key: 'plan_tomorrow', label: '\ud83d\udcc5 Plan tomorrow\'s service' },
  { key: 'journal', label: '\u270d\ufe0f Write in journal' }
]

const SUNDAY_CHECKLIST = [
  { key: 'read_twice', label: 'Read study article twice' },
  { key: 'underline', label: 'Underline key points and answers to study questions' },
  { key: 'research', label: 'Research unfamiliar references or cross-references' },
  { key: 'prepare_comments', label: 'Prepare 3-4 comments showing application to pioneer life' }
]

const SECTION_LABELS = [
  { key: 'treasures', label: '\ud83d\udc8e TREASURES FROM GOD\u2019S WORD', color: '#5b6abf' },
  { key: 'living', label: '\ud83d\udc9a LIVING AS CHRISTIANS', color: '#b5463c' }
]

const WEEKLY_MEETINGS = {
  '2026-02-09': {
    theme: 'He Is the Stability of Your Times',
    bibleReading: 'Isaiah 33-35',
    song: 'Song 3 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/',
    sundayArticle: 'The Book of Job Can Help You When You Give Counsel',
    sundayScriptures: [
      { ref: 'Job 33:1', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+33%3A1' },
      { ref: 'Job 4:7, 8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+4%3A7-8' },
      { ref: 'Job 42:7, 8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+42%3A7-8' },
      { ref: 'Prov. 27:9', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=proverbs+27%3A9' },
      { ref: 'Job 33:6, 7', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+33%3A6-7' }
    ],
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cHe Is the Stability of Your Times\u201d (10 min.) \u2014 Isa 33:6' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 35:8' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 35:1-10' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 60-61' }
      ]
    }
  },
  '2026-02-02': {
    theme: 'Jehovah Will Hear Your Cry for Help',
    bibleReading: 'Isaiah 30-32',
    song: 'Song 102 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-2-8-2026/',
    sundayArticle: 'The Book of Job Can Help You When You Suffer',
    sundayScriptures: [
      { ref: 'Job 34:12', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+34%3A12' },
      { ref: 'Job 4:7, 8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+4%3A7-8' },
      { ref: 'Eccl. 9:11', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=ecclesiastes+9%3A11' },
      { ref: 'Prov. 27:11', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=proverbs+27%3A11' },
      { ref: 'Heb. 4:12', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=hebrews+4%3A12' }
    ],
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cJehovah Will Hear Your Cry for Help\u201d (10 min.) \u2014 Isa 30:19' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 30:21' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 30:1-18' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 58-59' }
      ]
    }
  },
  '2026-02-16': {
    theme: 'Do Not Be Afraid of the Assyrian',
    bibleReading: 'Isaiah 36-38',
    song: 'Song 150 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/',
    sundayArticle: 'Imitate Jehovah\'s Humility',
    sundayScriptures: [
      { ref: 'Eph. 5:1', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=ephesians+5%3A1' },
      { ref: 'Ps. 113:5-8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalm+113%3A5-8' },
      { ref: 'Ps. 62:8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalm+62%3A8' },
      { ref: 'Mark 3:1-6', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=mark+3%3A1-6' },
      { ref: 'Ps. 138:6', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalm+138%3A6' }
    ],
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cDo Not Be Afraid of the Assyrian\u201d (10 min.) \u2014 Isa 37:6' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 38:8' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 36:1-22' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 62-63' }
      ]
    }
  }
}

function getWeekData(weekKey) {
  if (WEEKLY_MEETINGS[weekKey]) return WEEKLY_MEETINGS[weekKey]
  return {
    theme: '', bibleReading: '', song: 'Song and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
    sundayArticle: '', sundayScriptures: [],
    sections: {
      treasures: [{ id: 'talk', text: '\ud83c\udfa4 Talk (10 min.)' }, { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.)' }, { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.)' }],
      living: [{ id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' }, { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.)' }]
    }
  }
}

function ProgressRing({ progress, size = 60, strokeWidth = 6, color = '#818cf8' }) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const strokeDashoffset = circumference - (progress / 100) * circumference
  return (
    <svg width={size} height={size} className="progress-ring">
      <circle stroke="rgba(255,255,255,0.1)" strokeWidth={strokeWidth} fill="transparent" r={radius} cx={size / 2} cy={size / 2} />
      <circle stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" fill="transparent" r={radius} cx={size / 2} cy={size / 2}
        style={{ strokeDasharray: circumference, strokeDashoffset, transform: 'rotate(-90deg)', transformOrigin: '50% 50%', transition: 'stroke-dashoffset 0.5s ease' }} />
      <text x="50%" y="50%" textAnchor="middle" dy=".3em" fill="white" fontSize="14" fontWeight="600">{Math.round(progress)}%</text>
    </svg>
  )
}

export default function App() {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const weekLabel = formatRange(weekStart)
  const weekKey = toISO(weekStart)
  const weekData = getWeekData(weekKey)
  const prevWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }
  const nextWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }
  const [tab, setTab] = useState('home')
  const [checks, setChecks] = useState({})
  const [theme, setTheme] = useState('')
  const [bibleReading, setBibleReading] = useState('')
  const [scriptures, setScriptures] = useState('')
  const [comments, setComments] = useState('')
  const [treasuresComments, setTreasuresComments] = useState('')
  const [notes, setNotes] = useState('')
  const [sundayChecks, setSundayChecks] = useState({})
  const [sundayComments, setSundayComments] = useState('')
  const [sundayArticle, setSundayArticle] = useState('')
  const [journalDate, setJournalDate] = useState(todayStr())
  const [journalText, setJournalText] = useState('')
  const [journalTasks, setJournalTasks] = useState({})
  const [journalNotes, setJournalNotes] = useState('')
  const [morningChecks, setMorningChecks] = useState({})
  const [eveningChecks, setEveningChecks] = useState({})
  const [dailyText, setDailyText] = useState(null)
  const [dailyTextLoading, setDailyTextLoading] = useState(true)
  const [todos, setTodos] = useState([])
  const [newTodo, setNewTodo] = useState('')
    const [newTodoPriority, setNewTodoPriority] = useState('medium')
  const [newTodoDue, setNewTodoDue] = useState('')
  const [newTodoCategory, setNewTodoCategory] = useState('general')
  const [todoFilter, setTodoFilter] = useState('all')
  const morningProgress = Math.round((Object.values(morningChecks).filter(Boolean).length / MORNING_ROUTINE.length) * 100)
  const eveningProgress = Math.round((Object.values(eveningChecks).filter(Boolean).length / EVENING_ROUTINE.length) * 100)
  const loadWeek = useCallback(async () => {
    const wd = getWeekData(weekKey)
    const { data } = await supabase.from('weeks').select('*').eq('week_start', weekKey).maybeSingle()
    if (data) {
      setTheme(data.theme || wd.theme || ''); setBibleReading(data.bible_reading || wd.bibleReading || '')
      setScriptures(data.scriptures || ''); setComments(data.comments || ''); setTreasuresComments(data.treasures_comments || '')
      setNotes(data.notes || ''); setChecks(data.checks || {}); setSundayChecks(data.sunday_checks || {})
      setSundayComments(data.sunday_comments || ''); setSundayArticle(data.sunday_article || wd.sundayArticle || '')
    } else {
      setTheme(wd.theme || ''); setBibleReading(wd.bibleReading || ''); setScriptures(''); setComments('')
      setTreasuresComments(''); setNotes(''); setChecks({}); setSundayChecks({}); setSundayComments('')
      setSundayArticle(wd.sundayArticle || '')
    }
  }, [weekKey])
  useEffect(() => { loadWeek() }, [loadWeek])
  const saveWeek = useCallback(async () => {
    await supabase.from('weeks').upsert({ week_start: weekKey, theme, bible_reading: bibleReading, scriptures, comments, treasures_comments: treasuresComments, notes, checks, sunday_checks: sundayChecks, sunday_comments: sundayComments, sunday_article: sundayArticle }, { onConflict: 'week_start' })
  }, [weekKey, theme, bibleReading, scriptures, comments, treasuresComments, notes, checks, sundayChecks, sundayComments, sundayArticle])
  useEffect(() => { const t = setTimeout(saveWeek, 800); return () => clearTimeout(t) }, [saveWeek])
  const loadJournal = useCallback(async () => {
    const { data } = await supabase.from('journal_entries').select('*').eq('entry_date', journalDate).maybeSingle()
    if (data) {
      setJournalText(data.journal_text || ''); setJournalTasks(data.tasks || {}); setJournalNotes(data.notes || '')
      setMorningChecks(data.morning_checks || {}); setEveningChecks(data.evening_checks || {})
    } else { setJournalText(''); setJournalTasks({}); setJournalNotes(''); setMorningChecks({}); setEveningChecks({}) }
  }, [journalDate])
  useEffect(() => { loadJournal() }, [loadJournal])
  const saveJournal = useCallback(async () => {
    await supabase.from('journal_entries').upsert({ entry_date: journalDate, journal_text: journalText, tasks: journalTasks, notes: journalNotes, morning_checks: morningChecks, evening_checks: eveningChecks }, { onConflict: 'entry_date' })
  }, [journalDate, journalText, journalTasks, journalNotes, morningChecks, eveningChecks])
  useEffect(() => { const t = setTimeout(saveJournal, 800); return () => clearTimeout(t) }, [saveJournal])
  const loadTodos = useCallback(async () => {
    const { data } = await supabase.from('todo_items').select('*').order('created_at', { ascending: true })
    if (data) setTodos(data)
  }, [])
  useEffect(() => { loadTodos() }, [loadTodos])
    const addTodo = async () => { if (!newTodo.trim()) return; const ins = { text: newTodo.trim(), priority: newTodoPriority, category: newTodoCategory }; if (newTodoDue) ins.due_date = newTodoDue; const { data } = await supabase.from('todo_items').insert(ins).select().single(); if (data) setTodos(prev => [...prev, data]); setNewTodo(''); setNewTodoDue(''); setNewTodoPriority('medium'); setNewTodoCategory('general') }
  const toggleTodo = async (id, done) => { await supabase.from('todo_items').update({ done: !done }).eq('id', id); setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !done } : t)) }
  const deleteTodo = async (id) => { await supabase.from('todo_items').delete().eq('id', id); setTodos(prev => prev.filter(t => t.id !== id)) }
    const clearCompleted = async () => { const done = todos.filter(t => t.done); for (const t of done) { await supabase.from('todo_items').delete().eq('id', t.id) }; setTodos(prev => prev.filter(t => !t.done)) }
  const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 }
    const sortedTodos = [...todos].sort((a, b) => { if (a.done !== b.done) return a.done ? 1 : -1; const pa = PRIORITY_ORDER[a.priority || 'medium'] ?? 1; const pb = PRIORITY_ORDER[b.priority || 'medium'] ?? 1; return pa - pb })
  const filteredTodos = todoFilter === 'all' ? sortedTodos : todoFilter === 'active' ? sortedTodos.filter(t => !t.done) : sortedTodos.filter(t => t.done)
  const todoDoneCount = todos.filter(t => t.done).length
  const toggleCheck = (id) => setChecks(prev => ({ ...prev, [id]: !prev[id] }))
  const toggleSundayCheck = (key) => setSundayChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleMorning = (key) => setMorningChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleEvening = (key) => setEveningChecks(prev => ({ ...prev, [key]: !prev[key] }))
  useEffect(() => { fetch('/api/daily-text').then(r => r.ok ? r.json() : null).then(data => { setDailyText(data); setDailyTextLoading(false) }).catch(() => setDailyTextLoading(false)) }, [])
  const TABS = [
    { id: 'home', label: '\ud83c\udfe0 Home' },
    { id: 'morning', label: '\u2600\ufe0f Morning' },
    { id: 'evening', label: '\ud83c\udf19 Evening' },
    { id: 'prep', label: '\ud83d\udcdd Midweek' },
    { id: 'sunday', label: '\u26ea Sunday' },
    { id: 'todos', label: '\u2705 To-Do' },
    { id: 'journal', label: '\ud83d\udcd3 Journal' }
  ]

  return (
    <div className="app">
      <header className="header">
        <h1>Pioneer Spiritual Growth Tracker</h1>
        <p className="week-label">{weekLabel}</p>
        <div className="week-nav">
          <button onClick={prevWeek}>{"\u2190"} Prev Week</button>
          <button onClick={nextWeek}>Next Week {"\u2192"}</button>
        </div>
      </header>
      <nav className="tab-row">
        {TABS.map(t => (<button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>))}
      </nav>

      {tab === 'home' && (
        <div className="home-tab">
          <section className="card greeting-card">
            <h2 className="greeting-title">{getGreeting()}, Pioneer!</h2>
            <p className="greeting-date">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p>
          </section>
          <section className="card progress-card">
            <h3 className="section-heading">{"\ud83d\udcc8"} Today's Spiritual Progress</h3>
            <div className="progress-grid">
              <div className="progress-item" onClick={() => setTab('morning')}>
                <ProgressRing progress={morningProgress} color="#fbbf24" />
                <span className="progress-label">Morning</span>
              </div>
              <div className="progress-item" onClick={() => setTab('evening')}>
                <ProgressRing progress={eveningProgress} color="#818cf8" />
                <span className="progress-label">Evening</span>
              </div>
            </div>
          </section>
          <section className="card daily-text-card">
            <h3 className="section-heading">{"\ud83d\udcd6"} Daily Text</h3>
            {dailyTextLoading ? (<p className="daily-text-loading">Loading today's daily text...</p>) : dailyText ? (
              <div className="daily-text-content">
                <p className="daily-text-date">{dailyText.dateLabel}</p>
                <p className="daily-text-scripture"><em>{dailyText.scripture}</em></p>
                {dailyText.reference && <p className="daily-text-ref">{dailyText.reference}</p>}
                {dailyText.comment && <p className="daily-text-comment">{dailyText.comment.length > 200 ? dailyText.comment.slice(0, 200) + '...' : dailyText.comment}</p>}
                <a href={dailyText.wolUrl} target="_blank" rel="noopener noreferrer" className="workbook-link">Read Full Daily Text {"\u2192"}</a>
              </div>
            ) : (<div><p>Could not load daily text.</p><a href="https://wol.jw.org/en/wol/dt/r1/lp-e" target="_blank" rel="noopener noreferrer" className="workbook-link">View Daily Text on JW.org</a></div>)}
          </section>
          <section className="card">
            <h3 className="section-heading">{"\ud83d\ude80"} Quick Actions</h3>
            <div className="home-links">
              <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="workbook-btn">{"\ud83d\udcd6"} Meeting Workbook on JW.org</a>
              <button className="home-action-btn" onClick={() => setTab('prep')}>{"\ud83d\udcdd"} Go to Midweek Prep</button>
              <button className="home-action-btn" onClick={() => setTab('sunday')}>{"\u26ea"} Go to Sunday Meeting</button>
              <button className="home-action-btn" onClick={() => setTab('journal')}>{"\ud83d\udcd3"} Go to Daily Journal</button>
            </div>
          </section>
          <section className="card glance-card">
            <h3 className="section-heading">{"\ud83d\udcc5"} This Week at a Glance</h3>
            <p><strong>Theme:</strong> {weekData.theme || 'Not set'}</p>
            <p><strong>Bible Reading:</strong> {weekData.bibleReading || 'Not set'}</p>
            <p><strong>Song:</strong> {weekData.song}</p>
          </section>
        </div>
      )}

      {tab === 'morning' && (
        <div className="morning-tab">
          <section className="card">
            <h3 className="section-heading morning-heading">{"\u2600\ufe0f"} Morning Routine</h3>
            <p className="routine-date">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p>
            <div className="routine-verse"><em>"Trust in Jehovah with all your heart, and do not rely on your own understanding."</em> {"\u2014"} Proverbs 3:5</div>
            <div className="progress-summary">
              <ProgressRing progress={morningProgress} size={70} color="#fbbf24" />
              <span className="progress-text">{Object.values(morningChecks).filter(Boolean).length} of {MORNING_ROUTINE.length} completed</span>
            </div>
            {MORNING_ROUTINE.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!morningChecks[item.key]} onChange={() => toggleMorning(item.key)} /><span className={morningChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
          </section>
        </div>
      )}

      {tab === 'evening' && (
        <div className="evening-tab">
          <section className="card">
            <h3 className="section-heading evening-heading">{"\ud83c\udf19"} Evening Routine</h3>
            <p className="routine-date">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p>
            <div className="routine-verse"><em>"I will show a thankful attitude; I will sing praises to your name, O Most High."</em> {"\u2014"} Psalm 9:2</div>
            <div className="progress-summary">
              <ProgressRing progress={eveningProgress} size={70} color="#818cf8" />
              <span className="progress-text">{Object.values(eveningChecks).filter(Boolean).length} of {EVENING_ROUTINE.length} completed</span>
            </div>
            {EVENING_ROUTINE.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!eveningChecks[item.key]} onChange={() => toggleEvening(item.key)} /><span className={eveningChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
          </section>
        </div>
      )}

      {tab === 'prep' && (
        <div className="prep-tab">
          <section className="card meeting-card">
            <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="meeting-title-link"><h2>Our Christian Life & Ministry</h2></a>
            <p className="meeting-subtitle">Midweek Meeting {"\u2022"} {weekData.song}</p>
            <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="workbook-btn">{"\ud83d\udcd6"} View Meeting Workbook on JW.org</a>
            <label>Theme<input type="text" value={theme} onChange={e => setTheme(e.target.value)} placeholder={weekData.theme || "This week's main theme..."} /></label>
            <label>Bible Reading<input type="text" value={bibleReading} onChange={e => setBibleReading(e.target.value)} placeholder={weekData.bibleReading || 'e.g. Isaiah 31:1-9'} /></label>
          </section>
          {SECTION_LABELS.map(section => (
            <section key={section.key} className="card">
              <h3 className="section-heading" style={{ borderLeftColor: section.color }}>{section.label}</h3>
                          {weekData.sections[section.key].map(item => (<div key={item.id} className="meeting-part-item"><span>{item.text}</span></div>))}1
                          
              {section.key === 'treasures' && (<div className="treasures-comments"><h4 className="treasures-comments-title">{"\ud83d\udcdd"} My Bible Reading & Spiritual Gems Notes</h4><textarea rows={5} value={treasuresComments} onChange={e => setTreasuresComments(e.target.value)} placeholder="Write your Bible reading highlights, spiritual gems, and prepared comments..." /></div>)}
            </section>
          ))}
          <section className="card"><h3 className="section-heading notes-heading">Key Scriptures & References</h3><textarea rows={4} value={scriptures} onChange={e => setScriptures(e.target.value)} placeholder="Paste references and JW.org links here..." /></section>
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare</h3><textarea rows={5} value={comments} onChange={e => setComments(e.target.value)} placeholder="Write your prepared comments for the meeting..." /></section>
          <section className="card"><h3 className="section-heading notes-heading">Personal Study Notes</h3><textarea rows={4} value={notes} onChange={e => setNotes(e.target.value)} placeholder="What stood out to you this week?" /></section>
        </div>
      )}

      {tab === 'sunday' && (
        <div className="sunday-tab">
          <section className="card">
            <h3 className="section-heading sunday-heading">{"\u26ea"} Weekend Meeting (Public Talk & Watchtower Study)</h3>
            <div className="sunday-article-box"><p><strong>Watchtower Study Article:</strong> {sundayArticle || weekData.sundayArticle || 'Visit jw.org for latest articles'}</p><a href="https://www.jw.org/en/library/magazines/watchtower-study/" target="_blank" rel="noopener noreferrer" className="wt-link"><em>Visit jw.org for latest Watchtower study articles</em></a></div>
            {SUNDAY_CHECKLIST.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!sundayChecks[item.key]} onChange={() => toggleSundayCheck(item.key)} /><span className={sundayChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
          </section>
          {weekData.sundayScriptures && weekData.sundayScriptures.length > 0 && (<section className="card"><h3 className="section-heading notes-heading">Key Scriptures:</h3><ul className="scripture-list">{weekData.sundayScriptures.map(s => (<li key={s.ref}><a href={s.url} target="_blank" rel="noopener noreferrer" className="scripture-link">{s.ref}</a></li>))}</ul></section>)}
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare</h3><textarea rows={6} value={sundayComments} onChange={e => setSundayComments(e.target.value)} placeholder="Write your prepared comments for the Watchtower study here..." /></section>
          <button className="print-btn" onClick={() => window.print()}>Print Meeting Preparation</button>
        </div>
      )}


      {tab === 'todos' && (
        <div className="todo-tab">
          <section className="card">
            <h3 className="section-heading">{"\u2705"} To-Do List</h3>
            <div className="todo-stats">
              <span>{todoDoneCount} of {todos.length} completed</span>
              {todoDoneCount > 0 && <button className="clear-done-btn" onClick={clearCompleted}>Clear done</button>}
            </div>
            <div className="todo-input-row">
              <input type="text" value={newTodo} onChange={e => setNewTodo(e.target.value)} placeholder="Add a new task..." onKeyDown={e => e.key === 'Enter' && addTodo()} />
              <button className="todo-add-btn" onClick={addTodo}>Add</button>
            </div>
            <div className="todo-options-row">
              <select value={newTodoPriority} onChange={e => setNewTodoPriority(e.target.value)} className="todo-select">
                <option value="high">{"\ud83d\udd34"} High</option>
                <option value="medium">{"\ud83d\udfe1"} Medium</option>
                <option value="low">{"\ud83d\udfe2"} Low</option>
              </select>
              <select value={newTodoCategory} onChange={e => setNewTodoCategory(e.target.value)} className="todo-select">
                <option value="general">{"\ud83d\udccb"} General</option>
                <option value="ministry">{"\ud83d\udce3"} Ministry</option>
                <option value="study">{"\ud83d\udcd6"} Study</option>
                <option value="meeting">{"\u26ea"} Meeting</option>
                <option value="personal">{"\ud83c\udfaf"} Personal</option>
              </select>
              <input type="date" value={newTodoDue} onChange={e => setNewTodoDue(e.target.value)} className="todo-date" />
            </div>
                        <div className="todo-filter-row">
              <button className={`todo-filter-btn ${todoFilter === 'all' ? 'active' : ''}`} onClick={() => setTodoFilter('all')}>All ({todos.length})</button>
              <button className={`todo-filter-btn ${todoFilter === 'active' ? 'active' : ''}`} onClick={() => setTodoFilter('active')}>Active ({todos.length - todoDoneCount})</button>
              <button className={`todo-filter-btn ${todoFilter === 'done' ? 'active' : ''}`} onClick={() => setTodoFilter('done')}>Done ({todoDoneCount})</button>
            </div>
            {filteredTodos.length === 0 && <p className="todo-empty">{todoFilter === 'all' ? 'No tasks yet. Add one above!' : todoFilter === 'active' ? 'All tasks completed!' : 'No completed tasks.'}</p>}
            {filteredTodos.map(todo => (<div key={todo.id} className={`todo-item priority-${todo.priority || 'medium'}`}><label className="check-row"><input type="checkbox" checked={todo.done} onChange={() => toggleTodo(todo.id, todo.done)} /><span className={todo.done ? 'done' : ''}>{todo.text}</span></label><div className="todo-meta">{todo.due_date && <span className={`todo-due ${new Date(todo.due_date) < new Date() && !todo.done ? 'overdue' : ''}`}>{new Date(todo.due_date + 'T12:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric'})}</span>}<span className={`todo-priority-badge ${todo.priority || 'medium'}`}>{todo.priority === 'high' ? '!' : todo.priority === 'low' ? '\u25CB' : '\u25CF'}</span></div><button className="todo-delete-btn" onClick={() => deleteTodo(todo.id)}>{"\u2715"}</button></div>))}
          </section>
        </div>
      )}

      {tab === 'journal' && (
        <div className="journal-tab">
          <section className="card">
            <h3 className="section-heading notes-heading">{"\ud83d\udcd3"} Daily Journal</h3>
            <label>Date<input type="date" value={journalDate} onChange={e => setJournalDate(e.target.value)} /></label>
            <textarea rows={6} value={journalText} onChange={e => setJournalText(e.target.value)} placeholder="Write your thoughts, spiritual experiences, and reflections for the day..." />
            <h4 className="section-heading notes-heading">Extra Notes</h4>
            <textarea rows={3} value={journalNotes} onChange={e => setJournalNotes(e.target.value)} placeholder="Any additional notes..." />
          </section>
        </div>
      )}

      <footer className="footer"><p>Pioneer Spiritual Growth Tracker {"\u00a9"} 2026</p></footer>
    </div>
  )
}