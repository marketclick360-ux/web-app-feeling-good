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

function toISO(d) {
  return d.toISOString().slice(0, 10)
}

function todayStr() {
  return toISO(new Date())
}

/* --------- Meeting Sections Data --------- */
const TREASURES = {
  label: '\ud83d\udc8e TREASURES FROM GOD\u2019S WORD',
  color: '#5b6abf',
  items: [
    { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cHe Is the Stability of Your Times\u201d (10 min.) \u2014 Isa 33:6', type: 'check' },
    { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 35:8: What does \u201cthe Way of Holiness\u201d represent today?', type: 'check' },
    { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 35:1-10', type: 'check' },
  ]
}

const FIELD_MINISTRY = {
  label: '\ud83c\udf3e APPLY YOURSELF TO THE FIELD MINISTRY',
  color: '#c7953c',
  items: [
    { id: 'convo', text: '\ud83d\udde3\ufe0f Starting a Conversation (3 min.) \u2014 Public Witnessing: Invite person to a meeting', type: 'check' },
    { id: 'followup', text: '\ud83d\udd04 Following Up (4 min.) \u2014 House to House: Feature a video from Teaching Toolbox', type: 'check' },
    { id: 'student_talk', text: '\ud83c\udfa4 Talk (5 min.) \u2014 Theme: The Bible Teaches Us How to Pray', type: 'check' },
  ]
}

const LIVING = {
  label: '\ud83d\udc9a LIVING AS CHRISTIANS',
  color: '#b5463c',
  items: [
    { id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)', type: 'check' },
    { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 60-61', type: 'check' },
  ]
}

const ALL_SECTIONS = [TREASURES, FIELD_MINISTRY, LIVING]

/* daily spiritual tasks */
const DAILY_TASKS = [
  { key: 'dailyText', label: '\ud83d\udcc3 Read daily text' },
  { key: 'bibleReading', label: '\ud83d\udcd6 Personal Bible reading' },
  { key: 'fieldService', label: '\ud83d\udeb6 Field service' },
  { key: 'studiesContacted', label: '\ud83d\udc65 Studies contacted' },
  { key: 'prayer', label: '\ud83d\ude4f Personal prayer' },
]

/* --------- App --------- */
export default function App() {
  /* week navigation */
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const weekLabel = formatRange(weekStart)
  const weekKey = toISO(weekStart)

  const prevWeek = () => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() - 7)
    setWeekStart(d)
  }
  const nextWeek = () => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + 7)
    setWeekStart(d)
  }

  /* active tab */
  const [tab, setTab] = useState('prep')

  /* -- Meeting Prep state -- */
  const [checks, setChecks] = useState({})
  const [theme, setTheme] = useState('')
  const [bibleReading, setBibleReading] = useState('')
  const [scriptures, setScriptures] = useState('')
  const [comments, setComments] = useState('')
  const [notes, setNotes] = useState('')

  /* -- Journal state -- */
  const [journalDate, setJournalDate] = useState(todayStr())
  const [journalText, setJournalText] = useState('')
  const [journalTasks, setJournalTasks] = useState({})
  const [journalNotes, setJournalNotes] = useState('')

  /* progress calculation */
  const totalItems = ALL_SECTIONS.reduce((n, s) => n + s.items.length, 0)
  const doneItems = ALL_SECTIONS.reduce((n, s) => n + s.items.filter(i => checks[i.id]).length, 0)
  const pct = totalItems ? Math.round((doneItems / totalItems) * 100) : 0

  /* -- Supabase: load week data -- */
  const loadWeek = useCallback(async () => {
    const { data } = await supabase
      .from('weeks')
      .select('*')
      .eq('week_start', weekKey)
      .maybeSingle()
    if (data) {
      setTheme(data.theme || '')
      setBibleReading(data.bible_reading || '')
      setScriptures(data.scriptures || '')
      setComments(data.comments || '')
      setNotes(data.notes || '')
      setChecks(data.checks || {})
    } else {
      setTheme(''); setBibleReading(''); setScriptures('')
      setComments(''); setNotes(''); setChecks({})
    }
  }, [weekKey])

  useEffect(() => { loadWeek() }, [loadWeek])

  /* -- Supabase: save week (auto-save) -- */
  const saveWeek = useCallback(async () => {
    await supabase.from('weeks').upsert({
      week_start: weekKey,
      theme,
      bible_reading: bibleReading,
      scriptures,
      comments,
      notes,
      checks
    }, { onConflict: 'week_start' })
  }, [weekKey, theme, bibleReading, scriptures, comments, notes, checks])

  useEffect(() => {
    const t = setTimeout(saveWeek, 800)
    return () => clearTimeout(t)
  }, [saveWeek])

  /* -- Supabase: load journal -- */
  const loadJournal = useCallback(async () => {
    const { data } = await supabase
      .from('journal_entries')
      .select('*')
      .eq('entry_date', journalDate)
      .maybeSingle()
    if (data) {
      setJournalText(data.journal_text || '')
      setJournalTasks(data.tasks || {})
      setJournalNotes(data.notes || '')
    } else {
      setJournalText(''); setJournalTasks({}); setJournalNotes('')
    }
  }, [journalDate])

  useEffect(() => { loadJournal() }, [loadJournal])

  /* -- Supabase: save journal -- */
  const saveJournal = useCallback(async () => {
    await supabase.from('journal_entries').upsert({
      entry_date: journalDate,
      journal_text: journalText,
      tasks: journalTasks,
      notes: journalNotes
    }, { onConflict: 'entry_date' })
  }, [journalDate, journalText, journalTasks, journalNotes])

  useEffect(() => {
    const t = setTimeout(saveJournal, 800)
    return () => clearTimeout(t)
  }, [saveJournal])

  /* -- toggle helpers -- */
  const toggleCheck = (id) => {
    setChecks(prev => ({ ...prev, [id]: !prev[id] }))
  }
  const toggleJournalTask = (key) => {
    setJournalTasks(prev => ({ ...prev, [key]: !prev[key] }))
  }

  /* --------- render --------- */
  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <h1>Pioneer Spiritual Growth Tracker</h1>
        <p className="week-label">{weekLabel}</p>
        <div className="week-nav">
          <button onClick={prevWeek}>&larr; Prev Week</button>
          <button onClick={nextWeek}>Next Week &rarr;</button>
        </div>
      </header>

      {/* MEETING SUMMARY CARD */}
      <section className="card meeting-card">
        <h2>Our Christian Life &amp; Ministry</h2>
        <p className="meeting-subtitle">Midweek Meeting &bull; Song 3 and Prayer</p>
        <label>
          Theme
          <input
            type="text"
            value={theme}
            onChange={e => setTheme(e.target.value)}
            placeholder="He Is the Stability of Your Times"
          />
        </label>
        <label>
          Bible Reading
          <input
            type="text"
            value={bibleReading}
            onChange={e => setBibleReading(e.target.value)}
            placeholder="Isaiah 33-35"
          />
        </label>

        {/* PROGRESS BAR */}
        <div className="progress-wrap">
          <div className="progress-label">
            <span>Meeting Prep Progress</span>
            <span className="progress-pct">{pct}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${pct}%` }}
            />
          </div>
          {pct === 100 && <p className="congrats">\u2728 Great job! Fully prepared! \u2728</p>}
        </div>
      </section>

      {/* TAB BUTTONS */}
      <div className="tab-bar">
        <button
          className={tab === 'prep' ? 'tab active' : 'tab'}
          onClick={() => setTab('prep')}
        >
          Meeting Prep
        </button>
        <button
          className={tab === 'journal' ? 'tab active' : 'tab'}
          onClick={() => setTab('journal')}
        >
          Daily Journal
        </button>
      </div>

      {/* -- MEETING PREP TAB -- */}
      {tab === 'prep' && (
        <div className="prep-tab">
          {ALL_SECTIONS.map(section => (
            <section key={section.label} className="card section-card">
              <h3 className="section-heading" style={{ borderLeftColor: section.color }}>
                {section.label}
              </h3>
              {section.items.map(item => (
                <label key={item.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={!!checks[item.id]}
                    onChange={() => toggleCheck(item.id)}
                  />
                  <span className={checks[item.id] ? 'done' : ''}>{item.text}</span>
                </label>
              ))}
            </section>
          ))}

          {/* Key Scriptures */}
          <section className="card">
            <h3 className="section-heading notes-heading">Key Scriptures &amp; References</h3>
            <textarea
              rows={4}
              value={scriptures}
              onChange={e => setScriptures(e.target.value)}
              placeholder="Isa 33:6, Isa 35:8, w24.01 22... Paste references and JW.org links here..."
            />
          </section>

          {/* My Comments */}
          <section className="card">
            <h3 className="section-heading notes-heading">My Comments to Prepare</h3>
            <textarea
              rows={5}
              value={comments}
              onChange={e => setComments(e.target.value)}
              placeholder="Write your prepared comments for the meeting..."
            />
          </section>

          {/* Personal Notes */}
          <section className="card">
            <h3 className="section-heading notes-heading">Personal Study Notes</h3>
            <textarea
              rows={4}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="What stood out to you this week? Key lessons learned..."
            />
          </section>
        </div>
      )}

      {/* -- DAILY JOURNAL TAB -- */}
      {tab === 'journal' && (
        <div className="journal-tab">
          <section className="card">
            <h3 className="section-heading notes-heading">Daily Journal</h3>
            <label>
              Date
              <input
                type="date"
                value={journalDate}
                onChange={e => setJournalDate(e.target.value)}
              />
            </label>

            <textarea
              rows={6}
              value={journalText}
              onChange={e => setJournalText(e.target.value)}
              placeholder="Write your thoughts, spiritual experiences, and reflections for the day..."
            />

            <h3 className="section-heading notes-heading">Daily Spiritual Tasks</h3>
            {DAILY_TASKS.map(t => (
              <label key={t.key} className="check-row">
                <input
                  type="checkbox"
                  checked={!!journalTasks[t.key]}
                  onChange={() => toggleJournalTask(t.key)}
                />
                <span className={journalTasks[t.key] ? 'done' : ''}>{t.label}</span>
              </label>
            ))}

            <h3 className="section-heading notes-heading">Extra Notes</h3>
            <textarea
              rows={3}
              value={journalNotes}
              onChange={e => setJournalNotes(e.target.value)}
              placeholder="Any additional notes..."
            />
          </section>
        </div>
      )}

      <footer className="footer">
        <p>Pioneer Spiritual Growth Tracker &copy; 2026</p>
      </footer>
    </div>
  )
}
