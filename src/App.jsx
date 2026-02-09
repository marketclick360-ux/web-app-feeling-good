import { useState, useEffect, useCallback } from 'react'
import { supabase } from './supabaseClient'

/* ───────── helpers ───────── */
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
  return `${mon.toLocaleDateString('en-US', opts)} – ${sun.toLocaleDateString('en-US', opts)}, ${y}`
}

function toISO(d) {
  return d.toISOString().slice(0, 10)
}

function todayStr() {
  return toISO(new Date())
}

/* fixed meeting-prep checklist (same every week) */
const MEETING_TASKS = [
  'Read study article twice',
  'Underline key points and answers',
  'Research unfamiliar references',
  'Prepare 3-4 comments for discussion',
  'Review midweek meeting parts',
  'Practice any assigned parts'
]

/* ───────── App ───────── */
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

  /* ── Meeting Prep state ── */
  const [checks, setChecks] = useState({})
  const [theme, setTheme] = useState('')
  const [bibleReading, setBibleReading] = useState('')
  const [scriptures, setScriptures] = useState('')
  const [comments, setComments] = useState('')

  /* ── Journal state ── */
  const [journalDate, setJournalDate] = useState(todayStr())
  const [journalText, setJournalText] = useState('')
  const [journalTasks, setJournalTasks] = useState({
    dailyText: false,
    bibleReading: false,
    fieldService: false,
    studiesContacted: false
  })
  const [journalNotes, setJournalNotes] = useState('')

  /* ── Supabase: load week data ── */
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
      setChecks(data.checks || {})
    } else {
      setTheme('')
      setBibleReading('')
      setScriptures('')
      setComments('')
      setChecks({})
    }
  }, [weekKey])

  useEffect(() => { loadWeek() }, [loadWeek])

  /* ── Supabase: save week (auto-save on change) ── */
  const saveWeek = useCallback(async () => {
    await supabase.from('weeks').upsert({
      week_start: weekKey,
      theme,
      bible_reading: bibleReading,
      scriptures,
      comments,
      checks
    }, { onConflict: 'week_start' })
  }, [weekKey, theme, bibleReading, scriptures, comments, checks])

  useEffect(() => {
    const t = setTimeout(saveWeek, 800)
    return () => clearTimeout(t)
  }, [saveWeek])

  /* ── Supabase: load journal ── */
  const loadJournal = useCallback(async () => {
    const { data } = await supabase
      .from('journal_entries')
      .select('*')
      .eq('entry_date', journalDate)
      .maybeSingle()
    if (data) {
      setJournalText(data.journal_text || '')
      setJournalTasks(data.tasks || {
        dailyText: false,
        bibleReading: false,
        fieldService: false,
        studiesContacted: false
      })
      setJournalNotes(data.notes || '')
    } else {
      setJournalText('')
      setJournalTasks({
        dailyText: false,
        bibleReading: false,
        fieldService: false,
        studiesContacted: false
      })
      setJournalNotes('')
    }
  }, [journalDate])

  useEffect(() => { loadJournal() }, [loadJournal])

  /* ── Supabase: save journal ── */
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

  /* ── toggle helpers ── */
  const toggleCheck = (idx) => {
    setChecks(prev => ({ ...prev, [idx]: !prev[idx] }))
  }
  const toggleJournalTask = (key) => {
    setJournalTasks(prev => ({ ...prev, [key]: !prev[key] }))
  }

  /* ───────── render ───────── */
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
        <h2>Midweek Meeting (Life &amp; Ministry)</h2>
        <label>
          Theme
          <input
            type="text"
            value={theme}
            onChange={e => setTheme(e.target.value)}
            placeholder="This week's main theme..."
          />
        </label>
        <label>
          Bible Reading
          <input
            type="text"
            value={bibleReading}
            onChange={e => setBibleReading(e.target.value)}
            placeholder="e.g. Isaiah 31:1-9"
          />
        </label>
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

      {/* ── MEETING PREP TAB ── */}
      {tab === 'prep' && (
        <section className="card">
          <h3>Meeting Prep Checklist</h3>
          {MEETING_TASKS.map((task, i) => (
            <label key={i} className="check-row">
              <input
                type="checkbox"
                checked={!!checks[i]}
                onChange={() => toggleCheck(i)}
              />
              <span className={checks[i] ? 'done' : ''}>{task}</span>
            </label>
          ))}

          <h3>Key Scriptures</h3>
          <textarea
            rows={4}
            value={scriptures}
            onChange={e => setScriptures(e.target.value)}
            placeholder="Paste references and JW.org links here..."
          />

          <h3>My Comments to Prepare</h3>
          <textarea
            rows={5}
            value={comments}
            onChange={e => setComments(e.target.value)}
            placeholder="Write your prepared comments..."
          />
        </section>
      )}

      {/* ── DAILY JOURNAL TAB ── */}
      {tab === 'journal' && (
        <section className="card">
          <h3>Daily Journal</h3>
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
            placeholder="Write your thoughts for the day..."
          />

          <h3>Daily Tasks</h3>
          <label className="check-row">
            <input
              type="checkbox"
              checked={journalTasks.dailyText}
              onChange={() => toggleJournalTask('dailyText')}
            />
            <span className={journalTasks.dailyText ? 'done' : ''}>Daily text read</span>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={journalTasks.bibleReading}
              onChange={() => toggleJournalTask('bibleReading')}
            />
            <span className={journalTasks.bibleReading ? 'done' : ''}>Personal Bible reading</span>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={journalTasks.fieldService}
              onChange={() => toggleJournalTask('fieldService')}
            />
            <span className={journalTasks.fieldService ? 'done' : ''}>Field service</span>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={journalTasks.studiesContacted}
              onChange={() => toggleJournalTask('studiesContacted')}
            />
            <span className={journalTasks.studiesContacted ? 'done' : ''}>Studies contacted</span>
          </label>

          <h3>Extra Notes</h3>
          <textarea
            rows={3}
            value={journalNotes}
            onChange={e => setJournalNotes(e.target.value)}
            placeholder="Any additional notes..."
          />
        </section>
      )}

      <footer className="footer">
        <p>Pioneer Spiritual Growth Tracker &copy; 2026</p>
      </footer>
    </div>
  )
}
