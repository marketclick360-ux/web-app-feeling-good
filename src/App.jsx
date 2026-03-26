import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from './supabaseClient'
import RichNoteEditor from './RichNoteEditor'

/* ─── helpers ─────────────────────────────────────────── */
function mondayOf(date) {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff); d.setHours(0,0,0,0)
  return d
}
function formatRange(mon) {
  const sun = new Date(mon); sun.setDate(sun.getDate() + 6)
  const opts = { month: 'long', day: 'numeric' }
  return `${mon.toLocaleDateString('en-US', opts)} – ${sun.toLocaleDateString('en-US', opts)}, ${mon.getFullYear()}`
}
function toISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}
function todayStr() { return toISO(new Date()) }
function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good Morning'
  if (h < 17) return 'Good Afternoon'
  return 'Good Evening'
}

/* ─── constants ───────────────────────────────────────── */
const MORNING_ROUTINE = [
  { key: 'prayer_morning',  label: '🙏 Morning prayer' },
  { key: 'daily_text',      label: '📃 Read daily text' },
  { key: 'bible_reading',   label: '📖 Personal Bible reading' },
  { key: 'meditation',      label: '🧠 Meditate on a scripture' },
  { key: 'review_goals',    label: '🎯 Review pioneer goals for the day' },
  { key: 'prepare_service', label: '📼 Prepare for field service' },
]
const EVENING_ROUTINE = [
  { key: 'review_day',     label: '📝 Review the day in service' },
  { key: 'study_wt',       label: '📕 Study Watchtower or publication' },
  { key: 'meeting_prep',   label: '📚 Meeting preparation' },
  { key: 'prayer_evening', label: '🙏 Evening prayer of thanks' },
  { key: 'plan_tomorrow',  label: '📅 Plan tomorrow\'s service' },
  { key: 'journal',        label: '✍️ Write in journal' },
]
const SUNDAY_CHECKLIST = [
  { key: 'read_twice',        label: 'Read study article twice' },
  { key: 'underline',         label: 'Underline key points and answers to study questions' },
  { key: 'research',          label: 'Research unfamiliar references or cross-references' },
  { key: 'prepare_comments',  label: 'Prepare 3–4 comments showing application to pioneer life' },
]
const SECTION_LABELS = [
  { key: 'treasures', label: '💎 TREASURES FROM GOD'S WORD', color: '#5b6abf' },
  { key: 'living',    label: '💚 LIVING AS CHRISTIANS',       color: '#b5463c' },
]
const WEEKLY_MEETINGS = {
  '2026-02-09': {
    theme:'He Is the Stability of Your Times', bibleReading:'Isaiah 33-35', song:'Song 3 and Prayer',
    workbookUrl:'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-9-15-2026/',
    sundayArticle:'The Book of Job Can Help You When You Give Counsel',
    sundayScriptures:[{ref:'Job 33:1',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+33%3A1'},{ref:'Job 4:7, 8',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+4%3A7-8'},{ref:'Job 42:7, 8',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+42%3A7-8'},{ref:'Prov. 27:9',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=proverbs+27%3A9'},{ref:'Job 33:6, 7',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=job+33%3A6-7'}],
    sections:{treasures:[{id:'talk',text:'🎤 Talk: "He Is the Stability of Your Times" (10 min.) — Isa 33:6'},{id:'gems',text:'🔍 Spiritual Gems (10 min.) — Isa 35:8'},{id:'reading',text:'📖 Bible Reading (4 min.) — Isaiah 35:1-10'}],living:[{id:'local_needs',text:'📌 Local Needs (15 min.)'},{id:'cbs',text:'📕 Congregation Bible Study (30 min.) — lfb lessons 60-61'}]}
  },
  '2026-02-16': {
    theme:'Do Not Be Afraid Because of the Words That You Heard', bibleReading:'Isaiah 36-37', song:'Song 150 and Prayer',
    workbookUrl:'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/',
    sundayArticle:"Imitate Jehovah's Humility",
    sundayScriptures:[{ref:'Eph. 5:1',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=ephesians+5%3A1'},{ref:'Ps. 113:5-8',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+113%3A5-8'},{ref:'Ps. 62:8',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+62%3A8'},{ref:'Ps. 138:6',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+138%3A6'},{ref:'2 Pet. 3:9',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=2+peter+3%3A9'}],
    sections:{treasures:[{id:'talk',text:'🎤 Talk: "Do Not Be Afraid Because of the Words That You Heard" (10 min.) — Isa 36:1, 2; 37:6, 7'},{id:'gems',text:'🔍 Spiritual Gems (10 min.) — Isa 37:29'},{id:'reading',text:'📖 Bible Reading (4 min.) — Isaiah 37:14-23'}],living:[{id:'local_needs',text:'📌 "What Is the Basis for Your Confidence?" (15 min.)'},{id:'cbs',text:'📕 Congregation Bible Study (30 min.) — lfb lessons 62-63'}]}
  },
  '2026-02-23': {
    theme:'Like a Shepherd He Will Care For His Flock', bibleReading:'Isaiah 38-40', song:'Song 4 and Prayer',
    workbookUrl:'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-23-March-1-2026/',
    sundayArticle:'How to Plan a Wedding That Brings Honor to Jehovah',
    sundayScriptures:[{ref:'1 Cor. 14:40',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=1+corinthians+14%3A40'},{ref:'Prov. 5:18',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=proverbs+5%3A18'},{ref:'Gen. 2:24',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=genesis+2%3A24'},{ref:'Rom. 13:13',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=romans+13%3A13'},{ref:'1 John 2:15-17',url:'https://wol.jw.org/en/wol/l/r1/lp-e?q=1+john+2%3A15-17'}],
    sections:{treasures:[{id:'talk',text:'🎤 Talk: "Like a Shepherd He Will Care For His Flock" (10 min.) — Isa 40:8, 11, 26-29'},{id:'gems',text:'🔍 Spiritual Gems (10 min.) — Isa 40:3'},{id:'reading',text:'📖 Bible Reading (4 min.) — Isaiah 40:21-31'}],living:[{id:'local_needs',text:'📌 Annual Service Report (15 min.)'},{id:'cbs',text:'📕 Congregation Bible Study (30 min.) — lfb lessons 64-65'}]}
  },
}
const DEFAULT_WEEK = {
  theme:'', bibleReading:'', song:'Song and Prayer',
  workbookUrl:'https://www.jw.org/en/library/jw-meeting-workbook/',
  sundayArticle:'', sundayScriptures:[],
  sections:{
    treasures:[{id:'talk',text:'🎤 Talk (10 min.)'},{id:'gems',text:'🔍 Spiritual Gems (10 min.)'},{id:'reading',text:'📖 Bible Reading (4 min.)'}],
    living:[{id:'local_needs',text:'📌 Local Needs (15 min.)'},{id:'cbs',text:'📕 Congregation Bible Study (30 min.)'}],
  },
}

/* ─── ProgressRing ────────────────────────────────────── */
function ProgressRing({ progress, size=56, strokeWidth=5, color='#b8864a' }) {
  const r = (size - strokeWidth) / 2
  const circ = r * 2 * Math.PI
  return (
    <svg width={size} height={size} style={{display:'block'}}>
      <circle stroke="rgba(255,255,255,0.08)" strokeWidth={strokeWidth} fill="transparent" r={r} cx={size/2} cy={size/2} />
      <circle stroke={color} strokeWidth={strokeWidth} fill="transparent" r={r} cx={size/2} cy={size/2}
        strokeLinecap="round"
        style={{strokeDasharray:circ, strokeDashoffset:circ-(progress/100)*circ, transform:'rotate(-90deg)', transformOrigin:'50% 50%', transition:'stroke-dashoffset 0.5s ease'}} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" fill="rgba(255,255,255,0.75)" fontSize="12" fontWeight="400" fontFamily="'DM Mono',monospace">{Math.round(progress)}%</text>
    </svg>
  )
}

/* ─── Main App ────────────────────────────────────────── */
export default function App({ userId }) {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const weekLabel = formatRange(weekStart)
  const weekKey = toISO(weekStart)
  const [apiWeekData, setApiWeekData] = useState(null)
  const _raw = apiWeekData || WEEKLY_MEETINGS[weekKey] || DEFAULT_WEEK
  const weekData = { ...DEFAULT_WEEK, ..._raw, sections: { treasures: _raw.sections?.treasures ?? DEFAULT_WEEK.sections.treasures, living: _raw.sections?.living ?? DEFAULT_WEEK.sections.living } }
  const prevWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate()-7); setWeekStart(d) }
  const nextWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate()+7); setWeekStart(d) }

  const [journalDate, setJournalDate] = useState(todayStr())
  const prevDay = () => { const d = new Date(journalDate+'T12:00'); d.setDate(d.getDate()-1); setJournalDate(toISO(d)) }
  const nextDay = () => { const d = new Date(journalDate+'T12:00'); d.setDate(d.getDate()+1); setJournalDate(toISO(d)) }
  const goToday  = () => setJournalDate(todayStr())
  const isToday  = journalDate === todayStr()
  const displayDate = new Date(journalDate+'T12:00').toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'})

  const [tab, setTab] = useState(() => {
    if (typeof window === 'undefined') return 'morning'
    const s = window.localStorage.getItem('eps-active-tab')
    return ['morning','prep','sunday','todos'].includes(s) ? s : 'morning'
  })

  // ── week state
  const [checks, setChecks]                     = useState({})
  const [theme, setTheme]                       = useState('')
  const [bibleReading, setBibleReading]         = useState('')
  const [scriptures, setScriptures]             = useState('')
  const [comments, setComments]                 = useState('')
  const [treasuresComments, setTreasuresComments]   = useState('')
  const [treasuresComments2, setTreasuresComments2] = useState('')
  const [notes, setNotes]                       = useState('')
  const [sundayChecks, setSundayChecks]         = useState({})
  const [sundayComments, setSundayComments]     = useState('')
  const [sundayComments2, setSundayComments2]   = useState('')
  const [sundayComments3, setSundayComments3]   = useState('')
  const [sundayArticle, setSundayArticle]       = useState('')

  // ── daily state
  const [journalText, setJournalText]           = useState('')
  const [todoJournalText, setTodoJournalText]   = useState('')
  const [journalTasks, setJournalTasks]         = useState({})
  const [journalNotes, setJournalNotes]         = useState('')
  const [morningChecks, setMorningChecks]       = useState({})
  const [eveningChecks, setEveningChecks]       = useState({})
  const [morningGoals, setMorningGoals]         = useState('')
  const [eveningGoals, setEveningGoals]         = useState('')

  // ── api / ui
  const [dailyText, setDailyText]               = useState(null)
  const [dailyTextLoading, setDailyTextLoading] = useState(true)
  const [encouragement, setEncouragement]       = useState(null)
  const [todos, setTodos]                       = useState([])
  const [newTodo, setNewTodo]                   = useState('')
  const [newTodoPriority, setNewTodoPriority]   = useState('medium')
  const [newTodoDue, setNewTodoDue]             = useState(todayStr)
  const [newTodoCategory, setNewTodoCategory]   = useState('general')
  const [todoFilter, setTodoFilter]             = useState('all')
  const [editingTodoId, setEditingTodoId]       = useState(null)
  const [editingTodoText, setEditingTodoText]   = useState('')
  const [syncStatus, setSyncStatus]             = useState('Saved')
  const [isOnline, setIsOnline]                 = useState(() => typeof navigator === 'undefined' ? true : navigator.onLine)
  const [toasts, setToasts]                     = useState([])
  const [copiedId, setCopiedId]                 = useState(null)
  const [colorMode, setColorMode]               = useState(() => {
    if (typeof window === 'undefined') return ''
    return window.localStorage.getItem('eps-theme') === 'light' ? 'light-theme' : ''
  })
  const [showOnboarding, setShowOnboarding] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem('eps-onboarding-dismissed') !== '1'
  })

  const journalLoaded = useRef(false)
  const weekLoaded    = useRef(false)

  const morningProgress = Math.round((Object.values(morningChecks).filter(Boolean).length / MORNING_ROUTINE.length) * 100)
  const eveningProgress = Math.round((Object.values(eveningChecks).filter(Boolean).length / EVENING_ROUTINE.length) * 100)

  const pushToast = useCallback((message, tone='error') => {
    const id = Date.now() + Math.random()
    setToasts(p => [...p, {id, message, tone}])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4200)
  }, [])

  /* ── fetch meeting data ── */
  useEffect(() => {
    setApiWeekData(null)
    fetch(`/api/meeting-data?week=${weekKey}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setApiWeekData(d) })
      .catch(() => {})
  }, [weekKey])

  /* ── load / save week ── */
  const loadWeek = useCallback(async () => {
    if (!userId) return
    const wd = apiWeekData || WEEKLY_MEETINGS[weekKey] || DEFAULT_WEEK
    const { data, error } = await supabase.from('weeks').select('*').eq('week_start', weekKey).eq('user_id', userId).maybeSingle()
    if (error) { pushToast('Could not load weekly data.', 'error'); return }
    if (data) {
      setTheme(data.theme || wd.theme || ''); setBibleReading(data.bible_reading || wd.bibleReading || '')
      setScriptures(data.scriptures || ''); setComments(data.comments || '')
      setTreasuresComments(data.treasures_comments || ''); setTreasuresComments2(data.treasures_comments_2 || '')
      setNotes(data.notes || ''); setChecks(data.checks || {}); setSundayChecks(data.sunday_checks || {})
      setSundayComments(data.sunday_comments || ''); setSundayComments2(data.sunday_comments_2 || '')
      setSundayComments3(data.sunday_comments_3 || ''); setSundayArticle(data.sunday_article || wd.sundayArticle || '')
    } else if (!weekLoaded.current) {
      setTheme(wd.theme || ''); setBibleReading(wd.bibleReading || ''); setScriptures(''); setComments('')
      setTreasuresComments(''); setTreasuresComments2(''); setNotes(''); setChecks({}); setSundayChecks({})
      setSundayComments(''); setSundayComments2(''); setSundayComments3(''); setSundayArticle(wd.sundayArticle || '')
    }
    weekLoaded.current = true
  }, [weekKey, apiWeekData, userId, pushToast])

  useEffect(() => { weekLoaded.current = false; loadWeek() }, [loadWeek])

  const saveWeek = useCallback(async () => {
    if (!userId || !weekLoaded.current || !isOnline) { if (!isOnline) setSyncStatus('Offline'); return }
    setSyncStatus('Saving…')
    const { error } = await supabase.from('weeks').upsert({
      week_start: weekKey, user_id: userId, theme, bible_reading: bibleReading, scriptures, comments,
      treasures_comments: treasuresComments, treasures_comments_2: treasuresComments2, notes, checks,
      sunday_checks: sundayChecks, sunday_comments: sundayComments, sunday_comments_2: sundayComments2,
      sunday_comments_3: sundayComments3, sunday_article: sundayArticle
    }, { onConflict: 'week_start,user_id' })
    if (error) { setSyncStatus('Sync error'); pushToast('Could not save weekly notes.', 'error'); return }
    setSyncStatus('Saved')
  }, [weekKey, theme, bibleReading, scriptures, comments, treasuresComments, treasuresComments2, notes, checks, sundayChecks, sundayComments, sundayComments2, sundayComments3, sundayArticle, userId, isOnline, pushToast])

  useEffect(() => { const t = setTimeout(saveWeek, 800); return () => clearTimeout(t) }, [saveWeek])

  /* ── load / save journal ── */
  const loadJournal = useCallback(async () => {
    if (!userId) return
    const { data, error } = await supabase.from('journal_entries').select('*').eq('entry_date', journalDate).eq('user_id', userId).maybeSingle()
    if (error) { pushToast('Could not load journal.', 'error'); return }
    if (data) {
      setJournalText(data.journal_text || ''); setJournalTasks(data.tasks || {})
      setJournalNotes(data.notes || ''); setMorningChecks(data.morning_checks || {})
      setEveningChecks(data.evening_checks || ''); setMorningGoals(data.morning_goals || '')
      setEveningGoals(data.evening_goals || ''); setTodoJournalText(data.todo_journal_text || '')
    } else if (!journalLoaded.current) {
      setJournalText(''); setJournalTasks({}); setJournalNotes(''); setMorningChecks({})
      setEveningChecks({}); setMorningGoals(''); setEveningGoals(''); setTodoJournalText('')
    }
    journalLoaded.current = true
  }, [journalDate, userId, pushToast])

  useEffect(() => { journalLoaded.current = false; loadJournal() }, [loadJournal])

  const saveJournal = useCallback(async () => {
    if (!userId || !journalLoaded.current || !isOnline) { if (!isOnline) setSyncStatus('Offline'); return }
    setSyncStatus('Saving…')
    const { error } = await supabase.from('journal_entries').upsert({
      entry_date: journalDate, user_id: userId, journal_text: journalText, tasks: journalTasks,
      notes: journalNotes, morning_checks: morningChecks, evening_checks: eveningChecks,
      morning_goals: morningGoals, evening_goals: eveningGoals, todo_journal_text: todoJournalText
    }, { onConflict: 'entry_date,user_id' })
    if (error) { setSyncStatus('Sync error'); pushToast('Could not save journal.', 'error'); return }
    setSyncStatus('Saved')
  }, [journalDate, journalText, journalTasks, journalNotes, morningChecks, eveningChecks, morningGoals, eveningGoals, todoJournalText, userId, isOnline, pushToast])

  useEffect(() => { const t = setTimeout(saveJournal, 800); return () => clearTimeout(t) }, [saveJournal])

  /* ── todos ── */
  const loadTodos = useCallback(async () => {
    if (!userId) return
    const { data, error } = await supabase.from('todo_items').select('*').eq('user_id', userId).order('created_at', { ascending: true })
    if (error) { pushToast('Could not load tasks.', 'error'); return }
    if (data) setTodos(data)
  }, [userId, pushToast])

  useEffect(() => { loadTodos() }, [loadTodos])

  const addTodo = async () => {
    if (!userId) { pushToast('Please sign in to add tasks.', 'error'); return }
    if (!newTodo.trim()) return
    const ins = { text: newTodo.trim(), user_id: userId, priority: newTodoPriority, category: newTodoCategory, due_date: newTodoDue || todayStr() }
    const { data, error } = await supabase.from('todo_items').insert(ins).select().single()
    if (error) { pushToast('Could not add task.', 'error'); return }
    if (data) setTodos(p => [...p, data])
    setNewTodo(''); setNewTodoDue(todayStr()); setNewTodoPriority('medium'); setNewTodoCategory('general')
  }
  const toggleTodo = async (id, done) => {
    if (!userId) return
    const { error } = await supabase.from('todo_items').update({ done: !done }).eq('id', id)
    if (error) { pushToast('Could not update task.', 'error'); return }
    setTodos(p => p.map(t => t.id === id ? { ...t, done: !done } : t))
  }
  const deleteTodo = async (id) => {
    if (!userId) return
    if (!window.confirm('Delete this task?')) return
    const { error } = await supabase.from('todo_items').delete().eq('id', id)
    if (error) { pushToast('Could not delete task.', 'error'); return }
    setTodos(p => p.filter(t => t.id !== id))
    if (editingTodoId === id) { setEditingTodoId(null); setEditingTodoText('') }
  }
  const clearCompleted = async () => {
    if (!window.confirm('Delete all completed tasks?')) return
    const done = todos.filter(t => t.done); if (!done.length) return
    const { error } = await supabase.from('todo_items').delete().in('id', done.map(t => t.id))
    if (error) { pushToast('Could not clear tasks.', 'error'); return }
    setTodos(p => p.filter(t => !t.done))
  }
  const submitTodoEdit = async (id) => {
    if (!editingTodoText.trim()) { setEditingTodoId(null); return }
    const { error } = await supabase.from('todo_items').update({ text: editingTodoText.trim() }).eq('id', id)
    if (error) { pushToast('Could not save task.', 'error'); return }
    setTodos(p => p.map(t => t.id === id ? { ...t, text: editingTodoText.trim() } : t))
    setEditingTodoId(null); setEditingTodoText('')
  }

  const PRIORITY_ORDER = { high:0, medium:1, low:2 }
  const sortedTodos = [...todos].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1
    return (PRIORITY_ORDER[a.priority||'medium']??1) - (PRIORITY_ORDER[b.priority||'medium']??1)
  })
  const filteredTodos = todoFilter === 'all' ? sortedTodos : todoFilter === 'active' ? sortedTodos.filter(t => !t.done) : sortedTodos.filter(t => t.done)
  const todoDoneCount = todos.filter(t => t.done).length
  const todayIso = todayStr()

  /* ── toggle helpers ── */
  const toggleCheck        = id  => setChecks(p => ({...p, [id]: !p[id]}))
  const toggleSundayCheck  = key => setSundayChecks(p => ({...p, [key]: !p[key]}))
  const toggleMorning      = key => setMorningChecks(p => ({...p, [key]: !p[key]}))
  const toggleEvening      = key => setEveningChecks(p => ({...p, [key]: !p[key]}))

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id); setTimeout(() => setCopiedId(null), 1500)
    }).catch(() => pushToast('Copy failed.', 'warning'))
  }

  /* ── effects ── */
  useEffect(() => {
    const h = e => {
      const a = e.target.closest('a[href]'); if (!a) return
      const hr = a.getAttribute('href')
      if (hr && (hr.startsWith('http')||hr.startsWith('https')) && !hr.includes(window.location.hostname)) {
        e.preventDefault(); window.open(hr, '_blank', 'noopener,noreferrer')
      }
    }
    document.addEventListener('click', h); return () => document.removeEventListener('click', h)
  }, [])

  useEffect(() => {
    document.body.classList.toggle('light-theme', colorMode === 'light-theme')
    window.localStorage.setItem('eps-theme', colorMode === 'light-theme' ? 'light' : 'dark')
    return () => document.body.classList.remove('light-theme')
  }, [colorMode])

  useEffect(() => { window.localStorage.setItem('eps-active-tab', tab) }, [tab])

  useEffect(() => {
    const onOnline  = () => { setIsOnline(true);  pushToast('Back online.', 'ok') }
    const onOffline = () => { setIsOnline(false);  setSyncStatus('Offline'); pushToast('You are offline.', 'warning') }
    window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline)
    return () => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline) }
  }, [pushToast])

  useEffect(() => {
    let alive = true
    fetch('/api/daily-text').then(r => r.ok ? r.json() : null).then(d => { if (alive && d) setDailyText(d) }).catch(()=>{}).finally(() => { if (alive) setDailyTextLoading(false) })
    return () => { alive = false }
  }, [])

  useEffect(() => {
    let alive = true
    fetch('/api/encouragement').then(r => r.ok ? r.json() : null).then(d => { if (alive && d) setEncouragement(d) }).catch(()=>{})
    return () => { alive = false }
  }, [])

  /* ── week nav shared ── */
  const WeekNav = ({ thisBadge }) => (
    <div className="day-nav">
      <button className="day-nav-btn" onClick={prevWeek} aria-label="Previous week">◀</button>
      <span className="routine-date">{weekLabel}</span>
      <button className="day-nav-btn" onClick={nextWeek} aria-label="Next week">▶</button>
      {weekKey === toISO(mondayOf(new Date()))
        ? <span className="today-badge">This Week</span>
        : <button className="today-btn" onClick={() => setWeekStart(mondayOf(new Date()))}>This Week</button>}
    </div>
  )

  const TABS = [
    { id:'morning', icon:'☀️', name:'Morning' },
    { id:'prep',    icon:'📝', name:'Midweek' },
    { id:'sunday',  icon:'📖', name:'Sunday'  },
    { id:'todos',   icon:'✅', name:'To-Do'   },
  ]

  return (
    <div className={`app ${colorMode}`}>

      {/* ── TOP BAR ── */}
      <header className="top-bar">
        <div className="top-bar-brand">
          <span className="top-bar-title">Eat Pray Study</span>
          <span className="top-bar-sub">Pioneer Tracker</span>
        </div>
        <div className="top-bar-right">
          <div className={`sync-pill ${!isOnline ? 'offline' : syncStatus === 'Sync error' ? 'error' : ''}`} aria-live="polite">
            {!isOnline ? 'Offline' : syncStatus}
          </div>
          <button className="theme-toggle" onClick={() => setColorMode(colorMode === '' ? 'light-theme' : '')}
            aria-label="Toggle theme" title="Toggle light/dark">
            {colorMode === '' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      {/* ── TAB BAR ── */}
      <nav className="tab-row" aria-label="Primary tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)} aria-current={tab === t.id ? 'page' : undefined}>
            <span className="tab-icon">{t.icon}</span>
            <span className="tab-name">{t.name}</span>
          </button>
        ))}
      </nav>

      {/* ── TOASTS ── */}
      <div className="toast-stack" aria-live="polite">
        {toasts.map(t => <div key={t.id} className={`toast ${t.tone||'error'}`}>{t.message}</div>)}
      </div>

      {/* ════════════ MORNING TAB ════════════ */}
      {tab === 'morning' && (
        <div className="morning-tab">

          {showOnboarding && (
            <div className="card onboarding-card">
              <h3 className="section-heading morning-heading">✨ Quick Start</h3>
              <p className="onboarding-text">Use <strong>Morning</strong> for daily routines & journal, <strong>Midweek / Sunday</strong> for meeting prep, and <strong>To-Do</strong> for tasks. Everything auto-saves.</p>
              <button className="today-btn" onClick={() => { setShowOnboarding(false); window.localStorage.setItem('eps-onboarding-dismissed','1') }}>Got it</button>
            </div>
          )}

          {/* greeting */}
          <div className="card greeting-card">
            <div className="greeting-title">{getGreeting()}</div>
            <div className="greeting-date">{displayDate}</div>
            <div className="progress-grid">
              <div className="progress-item">
                <ProgressRing progress={morningProgress} color="#e2c88a" />
                <span className="progress-label">Morning</span>
              </div>
              <div className="progress-item">
                <ProgressRing progress={eveningProgress} color="#8ab88e" />
                <span className="progress-label">Evening</span>
              </div>
            </div>
          </div>

          {/* morning routine */}
          <div className="card">
            <h3 className="section-heading morning-heading">☀️ Morning Routine</h3>
            <div className="day-nav">
              <button className="day-nav-btn" onClick={prevDay} aria-label="Previous day">◀</button>
              <span className="routine-date">{displayDate}</span>
              <button className="day-nav-btn" onClick={nextDay} aria-label="Next day">▶</button>
              {isToday ? <span className="today-badge">Today</span> : <button className="today-btn" onClick={goToday}>Today</button>}
            </div>
            <label>Today's Goals
              <textarea rows={3} value={morningGoals} onChange={e => setMorningGoals(e.target.value)} placeholder="What are your spiritual goals for today?" />
            </label>
            <div style={{marginTop:'0.75rem'}}>
              {MORNING_ROUTINE.map(item => (
                <label key={item.key} className="check-row">
                  <input type="checkbox" checked={!!morningChecks[item.key]} onChange={() => toggleMorning(item.key)} />
                  <span className={morningChecks[item.key] ? 'done' : ''}>{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* evening routine */}
          <div className="card">
            <h3 className="section-heading evening-heading">🌙 Evening Routine</h3>
            <label>Evening Reflection
              <textarea rows={3} value={eveningGoals} onChange={e => setEveningGoals(e.target.value)} placeholder="How did your day go? What are you grateful for?" />
            </label>
            <div style={{marginTop:'0.75rem'}}>
              {EVENING_ROUTINE.map(item => (
                <label key={item.key} className="check-row">
                  <input type="checkbox" checked={!!eveningChecks[item.key]} onChange={() => toggleEvening(item.key)} />
                  <span className={eveningChecks[item.key] ? 'done' : ''}>{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* daily text */}
          <div className="card daily-text-card">
            <h3 className="section-heading morning-heading">📃 Daily Text</h3>
            {dailyTextLoading ? (
              <p className="daily-text-loading">Loading today's text…</p>
            ) : dailyText && dailyText.scripture ? (
              <>
                <p className="daily-text-date">{dailyText.dateLabel}</p>
                <p className="daily-text-scripture"><em>{dailyText.scripture || dailyText.note}</em></p>
                {dailyText.reference && <p className="daily-text-ref">{dailyText.reference}</p>}
                {(dailyText.comment || dailyText.note) && <p className="daily-text-comment">{(dailyText.comment||dailyText.note).slice(0,220)}{(dailyText.comment||dailyText.note).length > 220 ? '…' : ''}</p>}
                <a href={dailyText.wolUrl} className="workbook-link">Read full daily text →</a>
              </>
            ) : (
              <>
                <p className="daily-text-comment">Could not load daily text.</p>
                <a href="https://wol.jw.org/en/wol/dt/r1/lp-e" className="workbook-link">View on JW.org →</a>
              </>
            )}
          </div>

          {/* journal */}
          <div className="card">
            <h3 className="section-heading morning-heading">
              ✍️ Morning Journal
              <button className={`copy-btn ${copiedId==='mj'?'copied':''}`} onClick={() => copyToClipboard(journalText,'mj')}>
                {copiedId==='mj'?'✅':'📋'}
              </button>
            </h3>
            <RichNoteEditor value={journalText} onChange={setJournalText} placeholder="Write your thoughts, reflections, and spiritual experiences…" minHeight={200} />
          </div>

          {/* encouragement */}
          <div className="card">
            <h3 className="section-heading morning-heading">✨ Encouragement</h3>
            {encouragement ? (
              <>
                <p className="encouragement-verse"><em>{encouragement.text}</em></p>
                <p className="encouragement-ref">— {encouragement.reference}</p>
                <a href={encouragement.wolUrl} className="workbook-link">Read on JW.org →</a>
              </>
            ) : (
              <>
                <p className="encouragement-verse"><em>"Trust in Jehovah with all your heart, and do not rely on your own understanding."</em></p>
                <p className="encouragement-ref">— Proverbs 3:5</p>
              </>
            )}
          </div>

          {/* quick links */}
          <div className="card">
            <h3 className="section-heading">🔗 Quick Links</h3>
            <div className="quick-links-grid">
              <a href="https://www.jw.org" className="quick-link-btn">🌐 JW.org</a>
              <a href="https://wol.jw.org" className="quick-link-btn">📚 Online Library</a>
              <a href="https://www.jw.org/en/library/videos/#en/mediaitems/VODPgmEvtMorningWorship" className="quick-link-btn">🌅 Morning Worship</a>
              <a href="https://www.jw.org/en/library/music-songs/original-songs/" className="quick-link-btn">🎵 Songs</a>
            </div>
          </div>
        </div>
      )}

      {/* ════════════ MIDWEEK TAB ════════════ */}
      {tab === 'prep' && (
        <div className="prep-tab">
          <WeekNav />

          <div className="card meeting-card">
            <div className="meeting-subtitle">Midweek Meeting · {weekData.song}</div>
            <a href={weekData.workbookUrl} className="workbook-btn">📖 View Meeting Workbook on JW.org</a>
            <label>Theme
              <input type="text" value={theme} onChange={e => setTheme(e.target.value)} placeholder={weekData.theme || "This week's main theme…"} />
            </label>
            <label style={{marginTop:'0.75rem'}}>Bible Reading
              {bibleReading && <a href={`https://wol.jw.org/en/wol/l/r1/lp-e?q=${encodeURIComponent(bibleReading)}`} className="bible-link">📖</a>}
              <input type="text" value={bibleReading} onChange={e => setBibleReading(e.target.value)} placeholder={weekData.bibleReading || 'e.g. Isaiah 31:1-9'} />
            </label>
          </div>

          {SECTION_LABELS.map(section => (
            <div key={section.key} className="card">
              <h3 className="section-heading" style={{borderBottomColor: section.color+'55'}}>{section.label}</h3>
              {(weekData.sections[section.key] ?? []).map(item => (
                <div key={item.id} className="meeting-part-item">
                  <span>{item.text}</span>
                  <button className={`copy-btn ${copiedId===item.id?'copied':''}`} onClick={() => copyToClipboard(item.text, item.id)}>
                    {copiedId===item.id?'✅':'📋'}
                  </button>
                </div>
              ))}
              {section.key === 'treasures' && (
                <div className="treasures-comments">
                  <div className="treasures-comments-title">
                    📝 Bible Reading & Gems Notes
                    <button className={`copy-btn ${copiedId==='t1'?'copied':''}`} onClick={() => copyToClipboard(treasuresComments,'t1')}>{copiedId==='t1'?'✅':'📋'}</button>
                  </div>
                  <RichNoteEditor value={treasuresComments} onChange={setTreasuresComments} placeholder="Write your highlights and prepared comments…" minHeight={150} />
                  <div className="treasures-comments-title" style={{marginTop:'0.75rem'}}>
                    📝 Bible Reading & Gems Notes (2)
                    <button className={`copy-btn ${copiedId==='t2'?'copied':''}`} onClick={() => copyToClipboard(treasuresComments2,'t2')}>{copiedId==='t2'?'✅':'📋'}</button>
                  </div>
                  <RichNoteEditor value={treasuresComments2} onChange={setTreasuresComments2} placeholder="Additional notes…" minHeight={150} />
                </div>
              )}
            </div>
          ))}

          <div className="card">
            <h3 className="section-heading notes-heading">
              Key Scriptures & References
              <button className={`copy-btn ${copiedId==='sc'?'copied':''}`} onClick={() => copyToClipboard(scriptures,'sc')}>{copiedId==='sc'?'✅':'📋'}</button>
            </h3>
            <RichNoteEditor value={scriptures} onChange={setScriptures} placeholder="Paste references and JW.org links here…" />
          </div>

          <div className="card">
            <h3 className="section-heading notes-heading">
              My Comments to Prepare
              <button className={`copy-btn ${copiedId==='cm'?'copied':''}`} onClick={() => copyToClipboard(comments,'cm')}>{copiedId==='cm'?'✅':'📋'}</button>
            </h3>
            <RichNoteEditor value={comments} onChange={setComments} placeholder="Write your prepared comments…" minHeight={150} />
          </div>

          <div className="card">
            <h3 className="section-heading notes-heading">
              Personal Study Notes
              <button className={`copy-btn ${copiedId==='nt'?'copied':''}`} onClick={() => copyToClipboard(notes,'nt')}>{copiedId==='nt'?'✅':'📋'}</button>
            </h3>
            <RichNoteEditor value={notes} onChange={setNotes} placeholder="What stood out to you this week?" />
          </div>
        </div>
      )}

      {/* ════════════ SUNDAY TAB ════════════ */}
      {tab === 'sunday' && (
        <div className="sunday-tab">
          <WeekNav />

          <div className="card">
            <h3 className="section-heading sunday-heading">📖 Weekend Meeting</h3>
            <div className="sunday-article-box">
              <p><strong>Watchtower Study Article:</strong> {sundayArticle || weekData.sundayArticle || 'Visit jw.org for latest articles'}</p>
              <a href={weekData.sundayArticleUrl || 'https://www.jw.org/en/library/magazines/'} className="wt-link"><em>Visit jw.org for latest Watchtower study articles</em></a>
            </div>
            {SUNDAY_CHECKLIST.map(item => (
              <label key={item.key} className="check-row">
                <input type="checkbox" checked={!!sundayChecks[item.key]} onChange={() => toggleSundayCheck(item.key)} />
                <span className={sundayChecks[item.key] ? 'done' : ''}>{item.label}</span>
              </label>
            ))}
          </div>

          {weekData.sundayScriptures?.length > 0 && (
            <div className="card">
              <h3 className="section-heading notes-heading">Key Scriptures</h3>
              <ul className="scripture-list">
                {weekData.sundayScriptures.map(s => (
                  <li key={s.ref}>
                    <a href={s.url} className="scripture-link">{s.ref}</a>
                    <button className={`copy-btn ${copiedId==='sc-'+s.ref?'copied':''}`} onClick={() => copyToClipboard(s.ref+' '+s.url,'sc-'+s.ref)}>
                      {copiedId==='sc-'+s.ref?'✅':'📋'}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {[['sundayComments','My Comments to Prepare',sundayComments,setSundayComments],
            ['sundayComments2','My Comments to Prepare (2)',sundayComments2,setSundayComments2],
            ['sundayComments3','My Comments to Prepare (3)',sundayComments3,setSundayComments3]].map(([id,label,val,setter]) => (
            <div key={id} className="card">
              <h3 className="section-heading notes-heading">
                {label}
                <button className={`copy-btn ${copiedId===id?'copied':''}`} onClick={() => copyToClipboard(val,id)}>{copiedId===id?'✅':'📋'}</button>
              </h3>
              <RichNoteEditor value={val} onChange={setter} placeholder="Write your prepared comments here…" minHeight={180} />
            </div>
          ))}

          <button className="print-btn" onClick={() => window.print()}>Print Meeting Preparation</button>
        </div>
      )}

      {/* ════════════ TODOS TAB ════════════ */}
      {tab === 'todos' && (
        <div className="todo-tab">
          <div className="card">
            <h3 className="section-heading">✅ Tasks</h3>

            <div className="todo-input-row">
              <input type="text" value={newTodo} onChange={e => setNewTodo(e.target.value)}
                placeholder="Add a new task…" onKeyDown={e => e.key==='Enter' && addTodo()} />
              <button className="todo-add-btn" onClick={addTodo}>Add</button>
            </div>

            <div className="todo-options-row">
              <select value={newTodoPriority} onChange={e => setNewTodoPriority(e.target.value)} className="todo-select">
                <option value="high">🔴 High</option>
                <option value="medium">🟡 Medium</option>
                <option value="low">🟢 Low</option>
              </select>
              <select value={newTodoCategory} onChange={e => setNewTodoCategory(e.target.value)} className="todo-select">
                <option value="general">📋 General</option>
                <option value="ministry">📣 Ministry</option>
                <option value="study">📖 Study</option>
                <option value="meeting">🙏 Meeting</option>
                <option value="personal">🎯 Personal</option>
              </select>
              <input type="date" value={newTodoDue} onChange={e => setNewTodoDue(e.target.value)} className="todo-date" />
            </div>

            <div className="todo-filter-row">
              {[['all',`All (${todos.length})`],['active',`Active (${todos.length-todoDoneCount})`],['done',`Done (${todoDoneCount})`]].map(([f,label]) => (
                <button key={f} className={`todo-filter-btn ${todoFilter===f?'active':''}`} onClick={() => setTodoFilter(f)}>{label}</button>
              ))}
            </div>

            {todoDoneCount > 0 && (
              <div className="todo-stats">
                <span>{todoDoneCount} completed</span>
                <button className="clear-done-btn" onClick={clearCompleted}>Clear completed</button>
              </div>
            )}

            {filteredTodos.length === 0 && (
              <p className="todo-empty">
                {todoFilter==='all' ? 'No tasks yet. Add one above!' : todoFilter==='active' ? 'All tasks done!' : 'No completed tasks.'}
              </p>
            )}

            {filteredTodos.map(todo => {
              const isEditing = editingTodoId === todo.id
              return (
                <div key={todo.id} className={`todo-item priority-${todo.priority||'medium'}`}>
                  <label className="check-row">
                    <input type="checkbox" checked={todo.done} onChange={() => toggleTodo(todo.id, todo.done)} />
                    {isEditing ? (
                      <input type="text" className="todo-edit-input" value={editingTodoText}
                        onChange={e => setEditingTodoText(e.target.value)} autoFocus
                        onKeyDown={e => { if (e.key==='Enter') submitTodoEdit(todo.id); if (e.key==='Escape') { setEditingTodoId(null); setEditingTodoText('') } }} />
                    ) : (
                      <span className={todo.done?'done':''}>{todo.text}</span>
                    )}
                  </label>
                  <div className="todo-meta">
                    {todo.due_date && (
                      <span className={`todo-due ${todo.due_date < todayIso && !todo.done ? 'overdue' : ''}`}>
                        {new Date(todo.due_date+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})}
                      </span>
                    )}
                    <span className={`todo-priority-badge ${todo.priority||'medium'}`}>
                      {todo.priority==='high'?'!':todo.priority==='low'?'○':'●'}
                    </span>
                  </div>
                  {isEditing ? (
                    <>
                      <button className="todo-save-btn"   onClick={() => submitTodoEdit(todo.id)}>Save</button>
                      <button className="todo-cancel-btn" onClick={() => { setEditingTodoId(null); setEditingTodoText('') }}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="todo-edit-btn"   onClick={() => { setEditingTodoId(todo.id); setEditingTodoText(todo.text||'') }}>✏</button>
                      <button className="todo-delete-btn" onClick={() => deleteTodo(todo.id)}>✕</button>
                    </>
                  )}
                </div>
              )
            })}
          </div>

          <div className="card">
            <h3 className="section-heading notes-heading">
              ✍️ Journal
              <button className={`copy-btn ${copiedId==='tj'?'copied':''}`} onClick={() => copyToClipboard(todoJournalText,'tj')}>{copiedId==='tj'?'✅':'📋'}</button>
            </h3>
            <RichNoteEditor value={todoJournalText} onChange={setTodoJournalText} placeholder="End of day reflections and notes…" minHeight={200} />
          </div>
        </div>
      )}

      <footer className="footer"><p>Eat Pray Study © 2026</p></footer>
    </div>
  )
}
