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

const SECTION_LABELS = [
  { key: 'treasures', label: '\ud83d\udc8e TREASURES FROM GOD\u2019S WORD', color: '#5b6abf' },
  { key: 'ministry', label: '\ud83c\udf3e APPLY YOURSELF TO THE FIELD MINISTRY', color: '#c7953c' },
  { key: 'living', label: '\ud83d\udc9a LIVING AS CHRISTIANS', color: '#b5463c' }
]

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

const DAILY_TASKS = [
  { key: 'dailyText', label: '\ud83d\udcc3 Read daily text' },
  { key: 'bibleReading', label: '\ud83d\udcd6 Personal Bible reading' },
  { key: 'fieldService', label: '\ud83d\udeb6 Field service' },
  { key: 'studiesContacted', label: '\ud83d\udc65 Studies contacted' },
  { key: 'prayer', label: '\ud83d\ude4f Personal prayer' },
]

const WEEKLY_MEETINGS = {
  '2026-02-09': {
    theme: 'He Is the Stability of Your Times', bibleReading: 'Isaiah 33-35',
    song: 'Song 3 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/',
    sundayArticle: 'The Book of Job Can Help You When You Suffer',
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cHe Is the Stability of Your Times\u201d (10 min.) — Isa 33:6' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) — Isa 35:8: What does \u201cthe Way of Holiness\u201d represent today?' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) — Isaiah 35:1-10' }
      ],
      ministry: [
        { id: 'convo', text: '\ud83d\udde3\ufe0f Starting a Conversation (3 min.) — Public Witnessing: Invite person to a meeting' },
        { id: 'followup', text: '\ud83d\udd04 Following Up (4 min.) — House to House: Feature a video from Teaching Toolbox' },
        { id: 'student_talk', text: '\ud83c\udfa4 Talk (5 min.) — Theme: The Bible Teaches Us How to Pray' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) — lfb lessons 60-61' }
      ]
    }
  },
  '2026-02-02': {
    theme: 'Jehovah Will Hear Your Cry for Help', bibleReading: 'Isaiah 30-32',
    song: 'Song 102 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-2-8-2026/',
    sundayArticle: 'How the Book of Job Can Help You',
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cJehovah Will Hear Your Cry for Help\u201d (10 min.) — Isa 30:19' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) — Isa 30:21: How does Jehovah guide us today?' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) — Isaiah 30:1-18' }
      ],
      ministry: [
        { id: 'convo', text: '\ud83d\udde3\ufe0f Starting a Conversation (3 min.) — Door to door' },
        { id: 'followup', text: '\ud83d\udd04 Following Up (4 min.) — Return visit' },
        { id: 'student_talk', text: '\ud83c\udfa4 Talk (5 min.) — Student assignment' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) — lfb lessons 58-59' }
      ]
    }
  },
  '2026-02-16': {
    theme: 'Do Not Be Afraid of the Assyrian', bibleReading: 'Isaiah 36-38',
    song: 'Song 150 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/',
    sundayArticle: 'Strengthen Your Faith in the Last Days',
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cDo Not Be Afraid of the Assyrian\u201d (10 min.) — Isa 37:6' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) — Isa 38:8: What was the sign Jehovah gave Hezekiah?' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) — Isaiah 36:1-22' }
      ],
      ministry: [
        { id: 'convo', text: '\ud83d\udde3\ufe0f Starting a Conversation (3 min.) — Informal witnessing' },
        { id: 'followup', text: '\ud83d\udd04 Following Up (4 min.) — Making a return visit' },
        { id: 'student_talk', text: '\ud83c\udfa4 Talk (5 min.) — Student assignment' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) — lfb lessons 62-63' }
      ]
    }
  }
}

function getWeekData(weekKey) {
  if (WEEKLY_MEETINGS[weekKey]) return WEEKLY_MEETINGS[weekKey]
  return {
    theme: '', bibleReading: '', song: 'Song and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
    sundayArticle: '',
    sections: {
      treasures: [{ id: 'talk', text: '\ud83c\udfa4 Talk (10 min.)' }, { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.)' }, { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.)' }],
      ministry: [{ id: 'convo', text: '\ud83d\udde3\ufe0f Starting a Conversation (3 min.)' }, { id: 'followup', text: '\ud83d\udd04 Following Up (4 min.)' }, { id: 'student_talk', text: '\ud83c\udfa4 Talk (5 min.)' }],
      living: [{ id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' }, { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.)' }]
    }
  }
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

  // Load/save week data (midweek + sunday)
  const loadWeek = useCallback(async () => {
    const wd = getWeekData(weekKey)
    const { data } = await supabase.from('weeks').select('*').eq('week_start', weekKey).maybeSingle()
    if (data) {
      setTheme(data.theme || wd.theme || '')
      setBibleReading(data.bible_reading || wd.bibleReading || '')
      setScriptures(data.scriptures || '')
      setComments(data.comments || '')
      setTreasuresComments(data.treasures_comments || '')
      setNotes(data.notes || '')
      setChecks(data.checks || {})
      setSundayChecks(data.sunday_checks || {})
      setSundayComments(data.sunday_comments || '')
      setSundayArticle(data.sunday_article || wd.sundayArticle || '')
    } else {
      setTheme(wd.theme || ''); setBibleReading(wd.bibleReading || '')
      setScriptures(''); setComments(''); setTreasuresComments(''); setNotes(''); setChecks({})
      setSundayChecks({}); setSundayComments(''); setSundayArticle(wd.sundayArticle || '')
    }
  }, [weekKey])
  useEffect(() => { loadWeek() }, [loadWeek])

  const saveWeek = useCallback(async () => {
    await supabase.from('weeks').upsert({
      week_start: weekKey, theme, bible_reading: bibleReading,
      scriptures, comments, treasures_comments: treasuresComments, notes, checks,
      sunday_checks: sundayChecks, sunday_comments: sundayComments, sunday_article: sundayArticle
    }, { onConflict: 'week_start' })
  }, [weekKey, theme, bibleReading, scriptures, comments, treasuresComments, notes, checks, sundayChecks, sundayComments, sundayArticle])
  useEffect(() => { const t = setTimeout(saveWeek, 800); return () => clearTimeout(t) }, [saveWeek])

  // Load/save journal data (including morning/evening routines)
  const loadJournal = useCallback(async () => {
    const { data } = await supabase.from('journal_entries').select('*').eq('entry_date', journalDate).maybeSingle()
    if (data) {
      setJournalText(data.journal_text || ''); setJournalTasks(data.tasks || {}); setJournalNotes(data.notes || '')
      setMorningChecks(data.morning_checks || {}); setEveningChecks(data.evening_checks || {})
    } else {
      setJournalText(''); setJournalTasks({}); setJournalNotes('')
      setMorningChecks({}); setEveningChecks({})
    }
  }, [journalDate])
  useEffect(() => { loadJournal() }, [loadJournal])

  const saveJournal = useCallback(async () => {
    await supabase.from('journal_entries').upsert({
      entry_date: journalDate, journal_text: journalText, tasks: journalTasks, notes: journalNotes,
      morning_checks: morningChecks, evening_checks: eveningChecks
    }, { onConflict: 'entry_date' })
  }, [journalDate, journalText, journalTasks, journalNotes, morningChecks, eveningChecks])
  useEffect(() => { const t = setTimeout(saveJournal, 800); return () => clearTimeout(t) }, [saveJournal])

  // Load/manage todos
  const loadTodos = useCallback(async () => {
    const { data } = await supabase.from('todo_items').select('*').order('created_at', { ascending: true })
    if (data) setTodos(data)
  }, [])
  useEffect(() => { loadTodos() }, [loadTodos])

  const addTodo = async () => {
    if (!newTodo.trim()) return
    const { data } = await supabase.from('todo_items').insert({ text: newTodo.trim() }).select().single()
    if (data) setTodos(prev => [...prev, data])
    setNewTodo('')
  }

  const toggleTodo = async (id, done) => {
    await supabase.from('todo_items').update({ done: !done }).eq('id', id)
    setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !done } : t))
  }

  const deleteTodo = async (id) => {
    await supabase.from('todo_items').delete().eq('id', id)
    setTodos(prev => prev.filter(t => t.id !== id))
  }

  const toggleCheck = (id) => setChecks(prev => ({ ...prev, [id]: !prev[id] }))
  const toggleSundayCheck = (key) => setSundayChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleJournalTask = (key) => setJournalTasks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleMorning = (key) => setMorningChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleEvening = (key) => setEveningChecks(prev => ({ ...prev, [key]: !prev[key] }))

  useEffect(() => {
    fetch('/api/daily-text')
      .then(r => r.ok ? r.json() : null)
      .then(data => { setDailyText(data); setDailyTextLoading(false) })
      .catch(() => setDailyTextLoading(false))
  }, [])

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
          <button onClick={prevWeek}>← Prev Week</button>
          <button onClick={nextWeek}>Next Week →</button>
        </div>
      </header>

      {!['sunday','morning','evening'].includes(tab) && (
      <section className="card meeting-card">
        <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="meeting-title-link">
          <h2>Our Christian Life & Ministry</h2>
        </a>
        <p className="meeting-subtitle">Midweek Meeting • {weekData.song}</p>
        <a className="workbook-btn" href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer">
          {"\ud83d\udcd6"} View Meeting Workbook on JW.org
        </a>
        <label>Theme
          <input type="text" value={theme} onChange={e => setTheme(e.target.value)}
            placeholder={weekData.theme || "This week's main theme..."} />
        </label>
        <label>Bible Reading
          <input type="text" value={bibleReading} onChange={e => setBibleReading(e.target.value)}
            placeholder={weekData.bibleReading || 'e.g. Isaiah 31:1-9'} />
        </label>
      </section>
            )}

      <div className="tab-row">
        {TABS.map(t => (
          <button key={t.id} className={tab === t.id ? 'tab active' : 'tab'} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'home' && (
        <div className="home-tab">
          <section className="card">
            <h3 className="section-heading">{"\ud83c\udfe0"} Welcome Back, Pioneer!</h3>
            <p className="home-greeting">Use this app to stay organized with your weekly meeting preparation and daily spiritual routine.</p>
            <div className="home-links">
              <a className="workbook-btn" href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer">
                {"\ud83d\udcd6"} Meeting Workbook on JW.org
              </a>
              <button className="home-action-btn" onClick={() => setTab('prep')}>{"\ud83d\udcdd"} Go to Midweek Prep</button>
              <button className="home-action-btn" onClick={() => setTab('sunday')}>{"\u26ea"} Go to Sunday Meeting</button>
              <button className="home-action-btn" onClick={() => setTab('journal')}>{"\ud83d\udcd3"} Go to Daily Journal</button>
            </div>
          </section>

          <section className="card daily-text-card">
            <h3 className="section-heading">{"\ud83d\udcd6"} Daily Text</h3>
            {dailyTextLoading ? (
              <p className="daily-text-loading">Loading today's daily text...</p>
            ) : dailyText ? (
              <div className="daily-text-content">
                <p className="daily-text-date">{dailyText.dateLabel}</p>
                <p className="daily-text-scripture"><em>{dailyText.scripture}</em></p>
                {dailyText.reference && <p className="daily-text-ref">{dailyText.reference}</p>}
                {dailyText.comment && <p className="daily-text-comment">{dailyText.comment.length > 300 ? dailyText.comment.slice(0, 300) + '...' : dailyText.comment}</p>}
                <a href={dailyText.wolUrl} target="_blank" rel="noopener noreferrer" className="workbook-link">Read Full Daily Text on JW.org</a>
              </div>
            ) : (
              <div><p>Could not load daily text.</p>
                <a href="https://wol.jw.org/en/wol/dt/r1/lp-e" target="_blank" rel="noopener noreferrer">View Daily Text on JW.org</a></div>
            )}
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
        <div className="routine-tab">
          <section className="card">
            <h3 className="section-heading morning-heading">{"\u2600\ufe0f"} Morning Routine</h3>
            <p className="routine-date">Date: {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p>
            <p className="routine-verse"><em>"Trust in Jehovah with all your heart, and do not rely on your own understanding."</em> — Proverbs 3:5</p>
            {MORNING_ROUTINE.map(item => (
              <label key={item.key} className="check-row">
                <input type="checkbox" checked={!!morningChecks[item.key]} onChange={() => toggleMorning(item.key)} />
                <span className={morningChecks[item.key] ? 'done' : ''}>{item.label}</span>
              </label>
            ))}
          </section>
        </div>
      )}

      {tab === 'evening' && (
        <div className="routine-tab">
          <section className="card">
            <h3 className="section-heading evening-heading">{"\ud83c\udf19"} Evening Routine</h3>
            <p className="routine-date">Date: {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p>
            <p className="routine-verse"><em>"I will show a thankful attitude; I will sing praises to your name, O Most High."</em> — Psalm 9:2</p>
            {EVENING_ROUTINE.map(item => (
              <label key={item.key} className="check-row">
                <input type="checkbox" checked={!!eveningChecks[item.key]} onChange={() => toggleEvening(item.key)} />
                <span className={eveningChecks[item.key] ? 'done' : ''}>{item.label}</span>
              </label>
            ))}
          </section>
        </div>
      )}

      {tab === 'prep' && (
        <div className="prep-tab">
          <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="workbook-link">
            {"\ud83d\udcd6"} Open Meeting Workbook on JW.org
          </a>
          {SECTION_LABELS.filter(s => s.key !== 'ministry').map(section => (
            <section key={section.key} className="card">
              <h3 className="section-heading" style={{ borderLeftColor: section.color }}>{section.label}</h3>
              {weekData.sections[section.key].map(item => (
                <label key={item.id} className="check-row">
                  <input type="checkbox" checked={!!checks[item.id]} onChange={() => toggleCheck(item.id)} />
                  <span className={checks[item.id] ? 'done' : ''}>{item.text}</span>
                </label>
              ))}
              {section.key === 'treasures' && (
                <div className="treasures-comments">
                  <h4 className="treasures-comments-title">{"\ud83d\udcdd"} My Bible Reading & Spiritual Gems Notes</h4>
                  <textarea rows={5} value={treasuresComments} onChange={e => setTreasuresComments(e.target.value)}
                    placeholder="Write your Bible reading highlights, spiritual gems, and prepared comments for Treasures here..." />
                </div>
              )}
            </section>
          ))}
          <section className="card">
            <h3 className="section-heading notes-heading">Key Scriptures & References</h3>
            <textarea rows={4} value={scriptures} onChange={e => setScriptures(e.target.value)}
              placeholder="Paste references and JW.org links here..." />
          </section>
          <section className="card">
            <h3 className="section-heading notes-heading">My Comments to Prepare</h3>
            <textarea rows={5} value={comments} onChange={e => setComments(e.target.value)}
              placeholder="Write your prepared comments for the meeting..." />
          </section>
          <section className="card">
            <h3 className="section-heading notes-heading">Personal Study Notes</h3>
            <textarea rows={4} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="What stood out to you this week? Key lessons learned..." />
          </section>
        </div>
      )}

      {tab === 'sunday' && (
        <div className="sunday-tab">
          <section className="card">
            <h3 className="section-heading sunday-heading">{"\u26ea"} Weekend Meeting (Public Talk & Watchtower Study)</h3>
            <div className="sunday-article-box">
              <p><strong>Watchtower Study Article:</strong> {sundayArticle || weekData.sundayArticle || 'Visit jw.org for latest articles'}</p>
              <a href="https://www.jw.org/en/library/magazines/watchtower-study/" target="_blank" rel="noopener noreferrer" className="wt-link">
                <em>Visit jw.org for latest Watchtower study articles</em>
              </a>
            </div>
            {SUNDAY_CHECKLIST.map(item => (
              <label key={item.key} className="check-row">
                <input type="checkbox" checked={!!sundayChecks[item.key]} onChange={() => toggleSundayCheck(item.key)} />
                <span className={sundayChecks[item.key] ? 'done' : ''}>{item.label}</span>
              </label>
            ))}
          </section>
          <section className="card">
            <h3 className="section-heading notes-heading">My Comments to Prepare</h3>
            <textarea rows={6} value={sundayComments} onChange={e => setSundayComments(e.target.value)}
              placeholder="Write your prepared comments for the Watchtower study here..." />
          </section>
        </div>
      )}

      {tab === 'todos' && (
        <div className="todo-tab">
          <section className="card">
            <h3 className="section-heading">{"\u2705"} To-Do List</h3>
            <div className="todo-input-row">
              <input type="text" value={newTodo} onChange={e => setNewTodo(e.target.value)}
                placeholder="Add a new task..." onKeyDown={e => e.key === 'Enter' && addTodo()} />
              <button className="todo-add-btn" onClick={addTodo}>Add</button>
            </div>
            {todos.length === 0 && <p className="todo-empty">No tasks yet. Add one above!</p>}
            {todos.map(todo => (
              <div key={todo.id} className="todo-item">
                <label className="check-row">
                  <input type="checkbox" checked={todo.done} onChange={() => toggleTodo(todo.id, todo.done)} />
                  <span className={todo.done ? 'done' : ''}>{todo.text}</span>
                </label>
                <button className="todo-delete-btn" onClick={() => deleteTodo(todo.id)}>✕</button>
              </div>
            ))}
          </section>
        </div>
      )}

      {tab === 'journal' && (
        <div className="journal-tab">
          <section className="card">
            <h3 className="section-heading notes-heading">Daily Journal</h3>
            <label>Date
              <input type="date" value={journalDate} onChange={e => setJournalDate(e.target.value)} />
            </label>
            <textarea rows={6} value={journalText} onChange={e => setJournalText(e.target.value)}
              placeholder="Write your thoughts, spiritual experiences, and reflections for the day..." />
            <h3 className="section-heading notes-heading">Daily Spiritual Tasks</h3>
            {DAILY_TASKS.map(t => (
              <label key={t.key} className="check-row">
                <input type="checkbox" checked={!!journalTasks[t.key]} onChange={() => toggleJournalTask(t.key)} />
                <span className={journalTasks[t.key] ? 'done' : ''}>{t.label}</span>
              </label>
            ))}
            <h3 className="section-heading notes-heading">Extra Notes</h3>
            <textarea rows={3} value={journalNotes} onChange={e => setJournalNotes(e.target.value)}
              placeholder="Any additional notes..." />
          </section>
        </div>
      )}

      <footer className="footer">
        <p>Pioneer Spiritual Growth Tracker © 2026</p>
      </footer>
    </div>
  )
}