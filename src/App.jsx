import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from './supabaseClient'
import RichNoteEditor from './RichNoteEditor'
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
function toISO(d) { var y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),dd=String(d.getDate()).padStart(2,'0'); return y+'-'+m+'-'+dd }
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
  { key: 'meditation', label: '\ud83e\udde0 Meditate on a scripture' },
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
  '2026-02-16': {
    theme: 'Do Not Be Afraid Because of the Words That You Heard',
    bibleReading: 'Isaiah 36-37',
    song: 'Song 150 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-16-22-2026/',
        sundayArticle: 'Imitate Jehovah\'s Humility',
        sundayScriptures: [
      { ref: 'Eph. 5:1', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=ephesians+5%3A1' },
      { ref: 'Ps. 113:5-8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+113%3A5-8' },
      { ref: 'Ps. 62:8', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+62%3A8' },
      { ref: 'Ps. 138:6', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=psalms+138%3A6' },
      { ref: '2 Pet. 3:9', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=2+peter+3%3A9' }
    ],
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cDo Not Be Afraid Because of the Words That You Heard\u201d (10 min.) \u2014 Isa 36:1, 2; 37:6, 7' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 37:29' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 37:14-23' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc \u201cWhat Is the Basis for Your Confidence?\u201d (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 62-63' }
      ]
    }
  },
  '2026-02-23': {
    theme: 'Like a Shepherd He Will Care For His Flock',
    bibleReading: 'Isaiah 38-40',
    song: 'Song 4 and Prayer',
    workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/january-february-2026-mwb/Life-and-Ministry-Meeting-Schedule-for-February-23-March-1-2026/',
        sundayArticle: 'How to Plan a Wedding That Brings Honor to Jehovah',
        sundayScriptures: [
      { ref: '1 Cor. 14:40', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=1+corinthians+14%3A40' },
      { ref: 'Prov. 5:18', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=proverbs+5%3A18' },
      { ref: 'Gen. 2:24', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=genesis+2%3A24' },
      { ref: 'Rom. 13:13', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=romans+13%3A13' },
      { ref: '1 John 2:15-17', url: 'https://wol.jw.org/en/wol/l/r1/lp-e?q=1+john+2%3A15-17' }
    ],
    sections: {
      treasures: [
        { id: 'talk', text: '\ud83c\udfa4 Talk: \u201cLike a Shepherd He Will Care For His Flock\u201d (10 min.) \u2014 Isa 40:8, 11, 26-29' },
        { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.) \u2014 Isa 40:3' },
        { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.) \u2014 Isaiah 40:21-31' }
      ],
      living: [
        { id: 'local_needs', text: '\ud83d\udccc Annual Service Report (15 min.)' },
        { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.) \u2014 lfb lessons 64-65' }
      ]
    }
  }
}
const DEFAULT_WEEK = {
  theme: '', bibleReading: '', song: 'Song and Prayer',
  workbookUrl: 'https://www.jw.org/en/library/jw-meeting-workbook/',
  sundayArticle: '', sundayScriptures: [],
  sections: {
    treasures: [{ id: 'talk', text: '\ud83c\udfa4 Talk (10 min.)' }, { id: 'gems', text: '\ud83d\udd0d Spiritual Gems (10 min.)' }, { id: 'reading', text: '\ud83d\udcd6 Bible Reading (4 min.)' }],
    living: [{ id: 'local_needs', text: '\ud83d\udccc Local Needs (15 min.)' }, { id: 'cbs', text: '\ud83d\udcd5 Congregation Bible Study (30 min.)' }]
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
export default function App({ userId, onSignOut, onSignIn }) {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const weekLabel = formatRange(weekStart)
  const weekKey = toISO(weekStart)
  const [apiWeekData, setApiWeekData] = useState(null)
  const _raw = apiWeekData || DEFAULT_WEEK; const weekData = { ...DEFAULT_WEEK, ..._raw, sections: { treasures: (_raw.sections?.treasures ?? DEFAULT_WEEK.sections.treasures), living: (_raw.sections?.living ?? DEFAULT_WEEK.sections.living) } }
  const prevWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }
  const nextWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }
  const [journalDate, setJournalDate] = useState(todayStr())
  const prevDay = () => { const d = new Date(journalDate + 'T12:00'); d.setDate(d.getDate() - 1); setJournalDate(toISO(d)) }
  const nextDay = () => { const d = new Date(journalDate + 'T12:00'); d.setDate(d.getDate() + 1); setJournalDate(toISO(d)) }
  const goToday = () => setJournalDate(todayStr())
  const isToday = journalDate === todayStr()
  const displayDate = new Date(journalDate + 'T12:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  const [tab, setTab] = useState(() => {
    if (typeof window === 'undefined') return 'morning'
    const saved = window.localStorage.getItem('eps-active-tab')
    return ['morning', 'prep', 'sunday', 'todos'].includes(saved) ? saved : null
  })
  const [checks, setChecks] = useState({})
  const [theme, setTheme] = useState('')
  const [bibleReading, setBibleReading] = useState('')
  const [scriptures, setScriptures] = useState('')
  const [comments, setComments] = useState('')
  const [treasuresComments, setTreasuresComments] = useState('');
const [treasuresComments2, setTreasuresComments2] = useState('');

  const [notes, setNotes] = useState('')
  const [sundayChecks, setSundayChecks] = useState({})
    const [sundayComments, setSundayComments] = useState('')
  const [sundayComments2, setSundayComments2] = useState('')
  const [sundayComments3, setSundayComments3] = useState('')
  const [sundayArticle, setSundayArticle] = useState('')
    const [journalText, setJournalText] = useState('')
    const [todoJournalText, setTodoJournalText] = useState('')
  const [journalTasks, setJournalTasks] = useState({})
  const [journalNotes, setJournalNotes] = useState('')
  const [morningChecks, setMorningChecks] = useState({})
  const [eveningChecks, setEveningChecks] = useState({})
  const [morningGoals, setMorningGoals] = useState('')
  const [eveningGoals, setEveningGoals] = useState('')
  const [dailyText, setDailyText] = useState(null)
const [encouragement, setEncouragement] = useState(null)  
 const [dailyTextLoading, setDailyTextLoading] = useState(true)
  const [todos, setTodos] = useState([])
    const [colorMode, setColorMode] = useState(() => {
      if (typeof window === 'undefined') return ''
      return window.localStorage.getItem('eps-theme') === 'light' ? 'light-theme' : ''
    })
  const [newTodo, setNewTodo] = useState('')
  const [newTodoPriority, setNewTodoPriority] = useState('medium')
  const [newTodoDue, setNewTodoDue] = useState('')
  const [newTodoCategory, setNewTodoCategory] = useState('general')
  const [todoFilter, setTodoFilter] = useState('all')
    const [editingTodoId, setEditingTodoId] = useState(null)
  const [editingTodoText, setEditingTodoText] = useState('')
  const [syncStatus, setSyncStatus] = useState('Saved')
      const [showMenu, setShowMenu] = useState(false); const settingsRef = useRef(null); useEffect(() => { const handler = (e) => { if (settingsRef.current && !settingsRef.current.contains(e.target)) setShowMenu(false) }; document.addEventListener('mousedown', handler); return () => document.removeEventListener('mousedown', handler) }, [])
    const [showEvening, setShowEvening] = useState(false)
        const [showMorning, setShowMorning] = useState(false)
        const [isOnline, setIsOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  const [toasts, setToasts] = useState([])
  const [showOnboarding, setShowOnboarding] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem('eps-onboarding-dismissed') !== '1'
  })
  const journalLoaded = useRef(false); const weekLoaded = useRef(false); const todoJournalLoaded = useRef(false)
  const pushToast = useCallback((message, tone = 'error') => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, tone }])
    window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, tone === 'ok' ? 1500 : 4200)
  }, [])
  const morningProgress = Math.round((Object.values(morningChecks).filter(Boolean).length / MORNING_ROUTINE.length) * 100)
  const eveningProgress = Math.round((Object.values(eveningChecks).filter(Boolean).length / EVENING_ROUTINE.length) * 100)
  useEffect(() => {
    setApiWeekData(null)
    fetch(`/api/meeting-data?week=${weekKey}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setApiWeekData(data) })
      .catch(() => {})
  }, [weekKey])
  const loadWeek = useCallback(async () => {
    if (!userId) return;
    const wd = apiWeekData || DEFAULT_WEEK
const { data, error } = await supabase
  .from('weeks')
  .select('*')
  .eq('week_start', weekKey)
        .eq('user_id', userId)
  .maybeSingle()

if (error) {
  console.error('Error loading week:', error)
  pushToast('Could not load weekly preparation data.', 'error')
  return
}
    if (data) {
      setTheme(data.theme || wd.theme || ''); setBibleReading(data.bible_reading || wd.bibleReading || '')
      setScriptures(data.scriptures || ''); setComments(data.comments || ''); setTreasuresComments(data.treasures_comments || '')
      setTreasuresComments2(data.treasures_comments_2 || '')
      setNotes(data.notes || ''); setChecks(data.checks || {}); setSundayChecks(data.sunday_checks || {})
      setSundayComments(data.sunday_comments || ''); setSundayComments2(data.sunday_comments_2 || ''); setSundayComments3(data.sunday_comments_3 || ''); setSundayArticle(data.sunday_article || wd.sundayArticle || '')
    } else {
  // Only initialize defaults on first load to prevent overwriting saved data
  if (!weekLoaded.current) {
    setTheme(wd.theme || '');
    setBibleReading(wd.bibleReading || '');
    setScriptures('');
    setComments('');
    setTreasuresComments('');
    setTreasuresComments2('');
    setNotes('');
    setChecks({});
    setSundayChecks({});
    setSundayComments('');
    setSundayComments2('');
    setSundayComments3('');
    setSundayArticle(wd.sundayArticle || '');
  }
}
  weekLoaded.current = true; }, [weekKey, apiWeekData, userId, pushToast])
  useEffect(() => { weekLoaded.current = false; loadWeek() }, [loadWeek])
  const saveWeek = useCallback(async () => {
    if (!userId) return
    if (!weekLoaded.current) return
    if (!isOnline) {
      setSyncStatus('Offline')
      return
    }
    setSyncStatus('Saving...')
    const { error } = await supabase.from('weeks').upsert({
      week_start: weekKey, user_id: userId, theme, bible_reading: bibleReading, scriptures, comments,
      treasures_comments: treasuresComments, treasures_comments_2: treasuresComments2, notes, checks,
      sunday_checks: sundayChecks, sunday_comments: sundayComments, sunday_comments_2: sundayComments2,
      sunday_comments_3: sundayComments3, sunday_article: sundayArticle
    }, { onConflict: 'week_start,user_id' })
    if (error) {
      setSyncStatus('Sync error')
      pushToast('Could not save weekly notes. Please try again.', 'error')
      return
    }
    pushToast('\u2713 Saved', 'ok')
  }, [weekKey, theme, bibleReading, scriptures, comments, treasuresComments, treasuresComments2, notes, checks, sundayChecks, sundayComments, sundayComments2, sundayComments3, sundayArticle, userId, isOnline, pushToast])
  useEffect(() => { const t = setTimeout(saveWeek, 800); return () => clearTimeout(t) }, [saveWeek])
const loadJournal = useCallback(async () => {
    if (!userId) return;
  const { data, error } = await supabase
    .from('journal_entries')
    .select('*')
    .eq('entry_date', journalDate)
          .eq('user_id', userId)
    .maybeSingle()

  if (error) {
    console.error('Journal load error:', error)
    pushToast('Could not load journal data.', 'error')
    return
  }

  if (data) {
    setJournalText(data.journal_text || '')
    setJournalTasks(data.tasks || {})
    setJournalNotes(data.notes || '')
    setMorningChecks(data.morning_checks || {})
    setEveningChecks(data.evening_checks || {})
    setMorningGoals(data.morning_goals || '')
    setEveningGoals(data.evening_goals || '')
        
  } else {
    if (!journalLoaded.current) {
      setJournalText('')
      setJournalTasks({})
      setJournalNotes('')
      setMorningChecks({})
      setEveningChecks({})
      setMorningGoals('')
      setEveningGoals('')
            
    }
  }

  journalLoaded.current = true
}, [journalDate, userId, pushToast])
  useEffect(() => { journalLoaded.current = false; loadJournal() }, [loadJournal])
  const saveJournal = useCallback(async () => {
    if (!userId) return
    if (!journalLoaded.current) return
    if (!isOnline) {
      setSyncStatus('Offline')
      return
    }
    setSyncStatus('Saving...')
    const { error } = await supabase.from('journal_entries').upsert({
      entry_date: journalDate, user_id: userId, journal_text: journalText, tasks: journalTasks, notes: journalNotes,
      morning_checks: morningChecks, evening_checks: eveningChecks, morning_goals: morningGoals, evening_goals: eveningGoals
    }, { onConflict: 'entry_date,user_id' })
    if (error) {
      setSyncStatus('Sync error')
      pushToast('Could not save journal changes.', 'error')
      return
    }
    pushToast('\u2713 Saved', 'ok')
  }, [journalDate, journalText, journalTasks, journalNotes, morningChecks, eveningChecks, morningGoals, eveningGoals, userId, isOnline, pushToast])
  useEffect(() => { const t = setTimeout(saveJournal, 800); return () => clearTimeout(t) }, [saveJournal])
    const loadTodoJournal = useCallback(async () => {
    if (!userId) return
    const todayDate = todayStr()
    const { data } = await supabase.from('journal_entries').select('todo_journal_text').eq('entry_date', todayDate).eq('user_id', userId).maybeSingle()
    if (data) { setTodoJournalText(data.todo_journal_text || '') } else { if (!todoJournalLoaded.current) setTodoJournalText('') }
    todoJournalLoaded.current = true
  }, [userId])
  useEffect(() => { todoJournalLoaded.current = false; loadTodoJournal() }, [loadTodoJournal])
    const saveTodoJournal = useCallback(async () => {
    if (!userId) return
    if (!todoJournalLoaded.current) return
    if (!isOnline) return
    const todayDate = todayStr()
    const { data: existing } = await supabase.from('journal_entries').select('entry_date').eq('entry_date', todayDate).eq('user_id', userId).maybeSingle()
    if (existing) {
      await supabase.from('journal_entries').update({ todo_journal_text: todoJournalText }).eq('entry_date', todayDate).eq('user_id', userId)
    } else {
      await supabase.from('journal_entries').upsert({ entry_date: todayDate, user_id: userId, todo_journal_text: todoJournalText }, { onConflict: 'entry_date,user_id' })
    }
  }, [todoJournalText, userId, isOnline])
  useEffect(() => { const t = setTimeout(saveTodoJournal, 800); return () => clearTimeout(t) }, [saveTodoJournal])
  const loadTodos = useCallback(async () => {
    if (!userId) return
    const { data, error } = await supabase.from('todo_items').select('*').eq('user_id', userId).order('created_at', { ascending: true })
    if (error) {
      pushToast('Could not load to-do items.', 'error')
      return
    }
    if (data) setTodos(data)
  }, [userId, pushToast])
  useEffect(() => { loadTodos() }, [loadTodos])
  const addTodo = async () => {
    if (!userId) return
    if (!newTodo.trim()) return
    const ins = { text: newTodo.trim(), user_id: userId, priority: newTodoPriority, category: newTodoCategory }
    if (newTodoDue) ins.due_date = newTodoDue
    const { data, error } = await supabase.from('todo_items').insert(ins).select().single()
    if (error) {
      pushToast('Could not add task.', 'error')
      return
    }
    if (data) setTodos(prev => [...prev, data])
    setNewTodo('')
    setNewTodoDue('')
    setNewTodoPriority('medium')
    setNewTodoCategory('general')
  }
  const toggleTodo = async (id, done) => {
    if (!userId) return
    const { error } = await supabase.from('todo_items').update({ done: !done }).eq('id', id)
    if (error) {
      pushToast('Could not update task status.', 'error')
      return
    }
    setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !done } : t))
  }
  const deleteTodo = async (id) => {
    if (!userId) return
    if (!window.confirm('Delete this task permanently?')) return
    const { error } = await supabase.from('todo_items').delete().eq('id', id)
    if (error) {
      pushToast('Could not delete task.', 'error')
      return
    }
    setTodos(prev => prev.filter(t => t.id !== id))
    if (editingTodoId === id) { setEditingTodoId(null); setEditingTodoText('') }
  }
  const clearCompleted = async () => {
    if (!window.confirm('Delete all completed tasks?')) return
    const done = todos.filter(t => t.done)
    if (done.length === 0) return
    const { error } = await supabase.from('todo_items').delete().in('id', done.map(t => t.id))
    if (error) {
      pushToast('Could not clear completed tasks.', 'error')
      return
    }
    setTodos(prev => prev.filter(t => !t.done))
  }
  const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 }
    const editTodo = async (id, newText) => {
      if (!newText.trim()) return
      const { error } = await supabase.from('todo_items').update({ text: newText.trim() }).eq('id', id)
      if (error) {
        pushToast('Could not save task text.', 'error')
        return
      }
      setTodos(prev => prev.map(t => t.id === id ? { ...t, text: newText.trim() } : t))
      setEditingTodoId(null)
      setEditingTodoText('')
    }
  const startTodoEdit = (todo) => { setEditingTodoId(todo.id); setEditingTodoText(todo.text || '') }
  const cancelTodoEdit = () => { setEditingTodoId(null); setEditingTodoText('') }
  const submitTodoEdit = async (id) => {
    if (!editingTodoText.trim()) {
      cancelTodoEdit()
      return
    }
    await editTodo(id, editingTodoText)
  }
  const sortedTodos = [...todos].sort((a, b) => { if (a.done !== b.done) return a.done ? 1 : -1; const pa = PRIORITY_ORDER[a.priority || 'medium'] ?? 1; const pb = PRIORITY_ORDER[b.priority || 'medium'] ?? 1; return pa - pb })
  const filteredTodos = todoFilter === 'all' ? sortedTodos : todoFilter === 'active' ? sortedTodos.filter(t => !t.done) : sortedTodos.filter(t => t.done)
  const todoDoneCount = todos.filter(t => t.done).length
  const todayIso = todayStr()
  const toggleCheck = (id) => setChecks(prev => ({ ...prev, [id]: !prev[id] }))
  const toggleSundayCheck = (key) => setSundayChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleMorning = (key) => setMorningChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const toggleEvening = (key) => setEveningChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const [copiedId, setCopiedId] = useState(null)
  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 1500)
    }).catch(() => pushToast('Copy failed on this device.', 'warning'))
  }
  const dismissOnboarding = () => {
    setShowOnboarding(false)
    window.localStorage.setItem('eps-onboarding-dismissed', '1')
  }
  useEffect(() => {
    let alive = true
    fetch('/api/daily-text')
      .then(async (r) => {
        if (!r.ok) throw new Error('daily-text failed')
        return r.json()
      })
      .then(data => {
        if (!alive) return
        setDailyText(data)
      })
      .catch(() => {
        if (!alive) return
        pushToast('Could not load daily text right now.', 'warning')
      })
      .finally(() => { if (alive) setDailyTextLoading(false) })
    return () => { alive = false }
  }, [pushToast])
  useEffect(() => {
    let alive = true
    fetch('/api/encouragement')
      .then(async (r) => {
        if (!r.ok) throw new Error('encouragement failed')
        return r.json()
      })
      .then(data => {
        if (!alive) return
        setEncouragement(data)
      })
      .catch(() => {
        if (!alive) return
        pushToast('Could not load encouragement text.', 'warning')
      })
    return () => { alive = false }
  }, [pushToast])
    useEffect(() => { const h = (e) => { const a = e.target.closest('a[href]'); if (!a) return; const hr = a.getAttribute('href'); if (hr && (hr.startsWith('http://') || hr.startsWith('https://')) && !hr.includes(window.location.hostname)) { e.preventDefault(); window.open(hr, '_blank', 'noopener,noreferrer'); } }; document.addEventListener('click', h); return () => document.removeEventListener('click', h); }, [])
  useEffect(() => {
    const isLight = colorMode === 'light-theme'
    document.body.classList.toggle('light-theme', isLight)
    window.localStorage.setItem('eps-theme', isLight ? 'light' : 'dark')
    return () => document.body.classList.remove('light-theme')
  }, [colorMode])
  useEffect(() => {
    if (!window.visualViewport) return
    const syncZoomClass = () => {
      document.body.classList.toggle('zoomed-viewport', window.visualViewport.scale > 1.01)
    }
    syncZoomClass()
    window.visualViewport.addEventListener('resize', syncZoomClass)
    return () => {
      window.visualViewport.removeEventListener('resize', syncZoomClass)
      document.body.classList.remove('zoomed-viewport')
    }
  }, [])
  useEffect(() => {
    const isEditable = (el) => el && (
      el.tagName === 'INPUT' ||
      el.tagName === 'TEXTAREA' ||
      el.tagName === 'SELECT' ||
      el.isContentEditable
    )
    const onFocusIn = (e) => {
      if (isEditable(e.target)) document.body.classList.add('keyboard-open')
    }
    const onFocusOut = () => document.body.classList.remove('keyboard-open')
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      document.removeEventListener('focusin', onFocusIn)
      document.removeEventListener('focusout', onFocusOut)
      document.body.classList.remove('keyboard-open')
    }
  }, [])
  useEffect(() => {
    const onOnline = () => {
      setIsOnline(true)
      pushToast('Back online. Sync resumed.', 'ok')
    }
    const onOffline = () => {
      setIsOnline(false)
      setSyncStatus('Offline')
      pushToast('You are offline. Changes will sync when connection returns.', 'warning')
    }
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [pushToast])
  useEffect(() => {
    if (tab) window.localStorage.setItem('eps-active-tab', tab)
  }, [tab])
    const TABS = [
    { id: 'morning', icon: '\u2600\ufe0f', name: 'Morning' },
    { id: 'prep', icon: '\ud83d\udcdd', name: 'Midweek' },
    { id: 'sunday', icon: '\ud83d\udcd6', name: 'Sunday' },
    { id: 'todos', icon: '\u2705', name: 'To-Do' },
  ]
  return (
    <div className={`app ${colorMode}`}>
      {/* Top bar */}
      <div className="top-bar">
        {tab !== null && <button className="back-btn" onClick={() => setTab(null)} aria-label="Back to home">{"\u2190"}</button>}
        {tab !== null && <span className="section-title">{TABS.find(t => t.id === tab)?.icon} {TABS.find(t => t.id === tab)?.name}</span>}
        <div className="top-bar-right">
          <button className="theme-toggle" onClick={() => setColorMode(colorMode === '' ? 'light-theme' : '')} aria-label={colorMode === '' ? 'Switch to light mode' : 'Switch to dark mode'} title="Toggle light/dark mode">{colorMode === '' ? '\u2600\ufe0f' : '\ud83c\udf19'}</button>
          <div className="settings-menu-wrap" ref={settingsRef}>
            <button className="settings-btn" onClick={() => setShowMenu(!showMenu)} aria-label="Settings">{"\u2699\ufe0f"}</button>
            {showMenu && <div className="settings-dropdown">
              {onSignOut && <button onClick={() => { onSignOut(); setShowMenu(false) }}>Sign Out</button>}
              {onSignIn && <button onClick={() => { onSignIn(); setShowMenu(false) }}>Sign In</button>}
            </div>}
          </div>
        </div>
      </div>
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.tone || 'error'}`}>{t.message}</div>
        ))}
      </div>
            {tab === null && (
        <div className="home-view">
          <section className="card greeting-card">
            <h2 className="greeting-title">{getGreeting()}</h2>
            <p className="greeting-date">{displayDate}</p>
          </section>
          <div className="home-grid">
            {TABS.map(t => (
              <button key={t.id} className="home-card" onClick={() => setTab(t.id)}>
                <span className="home-card-icon">{t.icon}</span>
                <span className="home-card-name">{t.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      {tab === 'morning' && (
        <div className="morning-tab">
          {showOnboarding && (
            <section className="card onboarding-card">
              <h3 className="section-heading morning-heading">Quick Start</h3>
              <p className="onboarding-text">Use Morning for daily goals, Midweek/Sunday for meeting prep, and To-Do for action items. Your changes auto-save.</p>
              <button className="today-btn" onClick={dismissOnboarding}>Got it</button>
            </section>
          )}
          
        <section className="card greeting-card">
          <h2 className="greeting-title">{getGreeting()}</h2>
          <p className="greeting-date">{displayDate}</p>
        </section>
                    <section className="card daily-text-card">
            <h3 className="section-heading morning-heading">{"\ud83d\udcc3"} Daily Text</h3> {dailyTextLoading ? (
              <p className="daily-text-loading">Loading today's daily text...</p>
            ) : dailyText && (dailyText.dateLabel || dailyText.wolUrl || dailyText.scripture || dailyText.comment || dailyText.note) ? (
              <div className="daily-text-content">
                <p className="daily-text-date">{dailyText.dateLabel}</p>
                <p className="daily-text-scripture"><em>{dailyText.scripture || dailyText.note}</em></p>
                {dailyText.reference && <p className="daily-text-ref">{dailyText.reference}</p>}
                {(dailyText.comment || dailyText.note) && <p className="daily-text-comment">{(dailyText.comment || dailyText.note).length > 200 ? (dailyText.comment || dailyText.note).slice(0, 200) + '...' : (dailyText.comment || dailyText.note)}</p>}
                <a href={dailyText.wolUrl} target="_blank" rel="noopener noreferrer" className="workbook-link">Read Full Daily Text {"\u2192"}</a>
              </div>
            ) : (
              <div>
                <p>Could not load daily text.</p>
                <a href="https://wol.jw.org/en/wol/dt/r1/lp-e" target="_blank" rel="noopener noreferrer" className="workbook-link">View Daily Text on JW.org</a>
              </div>
            )}
          </section>
          
<section className="card">
                <h3 className="section-heading morning-heading" onClick={() => setShowMorning(!showMorning)} style={{cursor:'pointer'}}>
                                  {showMorning ? '\u25BC' : '\u25B6'} {"\u2600\ufe0f"} Morning Routine
                                                </h3>
                                                              {showMorning && (
                                                                              <>
            <div className="day-nav">
              <button onClick={prevDay} className="day-nav-btn" aria-label="Previous day">{"\u25C0"}</button>
              <span className="routine-date">{displayDate}</span>
              <button onClick={nextDay} className="day-nav-btn" aria-label="Next day">{"\u25B6"}</button>
                        {isToday ? <span className="today-badge">Today</span> : <button onClick={goToday} className="today-btn">Today</button>}
            </div>
            <h4 className="section-heading morning-heading">{"\ud83c\udfaf"} Today's Goals</h4>
            <textarea rows={3} value={morningGoals} onChange={e => setMorningGoals(e.target.value)} placeholder="What are your spiritual goals for today?" />
            {MORNING_ROUTINE.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!morningChecks[item.key]} onChange={() => toggleMorning(item.key)} /><span className={morningChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
                        </>
                                      )}
        </section>
                  <section className="card encouragement-card">
  <h3 className="section-heading">{"\u2728"} Encouragement</h3>
  {encouragement ? (
    <>
      <p className="encouragement-verse"><em>{encouragement.text}</em></p>
      <p className="encouragement-ref">{"\u2014"} {encouragement.reference}</p>
      <a href={encouragement.wolUrl} target="_blank" rel="noopener noreferrer" className="workbook-link">Read on JW.org →</a>
    </>
  ) : (
    <>
      <p className="encouragement-verse"><em>"Trust in Jehovah with all your heart, and do not rely on your own understanding."</em></p>
      <p className="encouragement-ref">{"\u2014"} Proverbs 3:5</p>
    </>
  )}
</section>

          <section className="card">
            <h3 className="section-heading morning-heading">{"\u270d\ufe0f"} Morning Journal<button className={`copy-btn ${copiedId === 'morningJournal' ? 'copied' : ''}`} onClick={() => copyToClipboard(journalText, 'morningJournal')} title="Copy journal" aria-label="Copy journal">{copiedId === 'morningJournal' ? '\u2705' : '\ud83d\udccb'}</button></h3>
            <RichNoteEditor value={journalText} onChange={setJournalText} placeholder="Write your thoughts, reflections, and spiritual experiences..." minHeight={200} />
          </section>

                <section className="card">
          <h3 className="section-heading evening-heading" onClick={() => setShowEvening(!showEvening)} style={{cursor:'pointer'}}>
            {showEvening ? '\u25BC' : '\u25B6'} {"\ud83c\udf19"} Evening Routine
          </h3>
          {showEvening && (
            <>
              <h4 className="section-heading evening-heading">{"\ud83c\udfaf"} Evening Reflection</h4>
              <textarea rows={3} value={eveningGoals} onChange={e => setEveningGoals(e.target.value)} placeholder="How did your day go? What are you grateful for?" />
              {EVENING_ROUTINE.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!eveningChecks[item.key]} onChange={() => toggleEvening(item.key)} /><span className={eveningChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
            </>
          )}
        </section>
          

          <section className="card">
            <h3 className="section-heading" style={{borderLeftColor: '#e0a800'}}>{"\ud83d\udd17"} Quick Links</h3>
            <div className="quick-links-grid">
              <a href="https://www.jw.org" target="_blank" rel="noopener noreferrer" className="quick-link-btn">{"\ud83c\udf10"} JW.org</a>
              <a href="https://wol.jw.org" target="_blank" rel="noopener noreferrer" className="quick-link-btn">{"\ud83d\udcda"} Online Library</a>
                          <a href="https://www.jw.org/en/library/videos/#en/mediaitems/VODPgmEvtMorningWorship" target="_blank" rel="noopener noreferrer" className="quick-link-btn">{"\ud83c\udf05"} Morning Worship</a>
              <a href="https://www.jw.org/en/library/music-songs/original-songs/" target="_blank" rel="noopener noreferrer" className="quick-link-btn">{"\ud83c\udfb5"} Original Songs</a>
            </div>
          </section>
        </div>
      )}
      {tab === 'prep' && (
        <div className="prep-tab"> <div className="day-nav"> <button onClick={prevWeek} className="day-nav-btn" aria-label="Previous week">{"\u25C0"}</button> <span className="routine-date">{weekLabel}</span> <button onClick={nextWeek} className="day-nav-btn" aria-label="Next week">{"\u25B6"}</button> {weekKey === toISO(mondayOf(new Date())) ? <span className="today-badge">This Week</span> : <button onClick={() => setWeekStart(mondayOf(new Date()))} className="today-btn">Go to This Week</button>} </div>
          <section className="card meeting-card"> <p className="meeting-subtitle">Midweek Meeting {"\u2022"} {weekData.song}</p>
            <a href={weekData.workbookUrl} target="_blank" rel="noopener noreferrer" className="workbook-btn">{"\ud83d\udcd6"} View Meeting Workbook on JW.org</a>
            <label>Theme<input type="text" value={theme} onChange={e => setTheme(e.target.value)} placeholder={weekData.theme || "This week's main theme..."} /></label>
            <label>Bible Reading {bibleReading && <a href={`https://wol.jw.org/en/wol/l/r1/lp-e?q=${encodeURIComponent(bibleReading)}`} target="_blank" rel="noopener noreferrer" className="bible-link">📖</a>}<input type="text" value={bibleReading} onChange={e => setBibleReading(e.target.value)} placeholder={weekData.bibleReading || 'e.g. Isaiah 31:1-9'} /></label>
          </section>
          {SECTION_LABELS.map(section => (
            <section key={section.key} className="card">
              <h3 className="section-heading" style={{ borderLeftColor: section.color }}>{section.label}</h3>
              {(weekData.sections[section.key] ?? []).map(item => (<div key={item.id} className="meeting-part-item"><span>{item.text}</span><button className={`copy-btn ${copiedId === item.id ? 'copied' : ''}`} onClick={() => copyToClipboard(item.text, item.id)} title="Copy text" aria-label="Copy text">{copiedId === item.id ? '\u2705' : '\ud83d\udccb'}</button></div>))}
              {section.key === 'treasures' && (<div className="treasures-comments"><h4 className="treasures-comments-title">{"\ud83d\udcdd"} My Bible Reading & Spiritual Gems Notes<button className={`copy-btn ${copiedId === 'treasures' ? 'copied' : ''}`} onClick={() => copyToClipboard(treasuresComments, 'treasures')} title="Copy notes" aria-label="Copy notes">{copiedId === 'treasures' ? '\u2705' : '\ud83d\udccb'}</button></h4><RichNoteEditor value={treasuresComments} onChange={setTreasuresComments} placeholder="Write your Bible reading highlights, spiritual gems, and prepared comments..." minHeight={150} /></div>)}
            {section.key === 'treasures' && (
  <div className="treasures-comments">
    <h4 className="treasures-comments-title">
      {"📝"} My Bible Reading & Spiritual Gems Notes (2)
      <button
        className={`copy-btn ${copiedId === 'treasures2' ? 'copied' : ''}`}
        onClick={() => copyToClipboard(treasuresComments2, 'treasures2')}
        title="Copy notes"
        aria-label="Copy notes"
      >
        {copiedId === 'treasures2' ? '✅' : '📋'}
      </button>
    </h4>
    <RichNoteEditor
      value={treasuresComments2}
      onChange={setTreasuresComments2}
      placeholder="Write your Bible reading highlights, spiritual gems, and prepared comments..."
      minHeight={150}
    />
  </div>
)}
            </section>
          ))}
          <section className="card"><h3 className="section-heading notes-heading">Key Scriptures & References<button className={`copy-btn ${copiedId === 'scriptures' ? 'copied' : ''}`} onClick={() => copyToClipboard(scriptures, 'scriptures')} title="Copy scriptures" aria-label="Copy scriptures">{copiedId === 'scriptures' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={scriptures} onChange={setScriptures} placeholder="Paste references and JW.org links here..." /></section>
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare<button className={`copy-btn ${copiedId === 'comments' ? 'copied' : ''}`} onClick={() => copyToClipboard(comments, 'comments')} title="Copy comments" aria-label="Copy comments">{copiedId === 'comments' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={comments} onChange={setComments} placeholder="Write your prepared comments for the meeting..." minHeight={150} /></section>
          <section className="card"><h3 className="section-heading notes-heading">Personal Study Notes<button className={`copy-btn ${copiedId === 'notes' ? 'copied' : ''}`} onClick={() => copyToClipboard(notes, 'notes')} title="Copy notes" aria-label="Copy notes">{copiedId === 'notes' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={notes} onChange={setNotes} placeholder="What stood out to you this week?" /></section>
        </div>
      )}
      {tab === 'sunday' && (
        <div className="sunday-tab">
          <div className="day-nav">
            <button onClick={prevWeek} className="day-nav-btn" aria-label="Previous week">{"\u25C0"}</button>
            <span className="routine-date">{weekLabel}</span>
            <button onClick={nextWeek} className="day-nav-btn" aria-label="Next week">{"\u25B6"}</button>
            {weekKey === toISO(mondayOf(new Date())) ? <span className="today-badge">This Week</span> : <button onClick={() => setWeekStart(mondayOf(new Date()))} className="today-btn">Go to This Week</button>}
          </div>
          <section className="card">
            <h3 className="section-heading sunday-heading">{"\ud83d\udcd6"} Weekend Meeting (Public Talk & Watchtower Study)</h3>
            <div className="sunday-article-box"><p><strong>Watchtower Study Article:</strong> {sundayArticle || weekData.sundayArticle || 'Visit jw.org for latest articles'}</p><a href={weekData.sundayArticleUrl || "https://www.jw.org/en/library/magazines/"} target="_blank" rel="noopener noreferrer" className="wt-link"><em>Visit jw.org for latest Watchtower study articles</em></a></div>
            {SUNDAY_CHECKLIST.map(item => (<label key={item.key} className="check-row"><input type="checkbox" checked={!!sundayChecks[item.key]} onChange={() => toggleSundayCheck(item.key)} /><span className={sundayChecks[item.key] ? 'done' : ''}>{item.label}</span></label>))}
          </section>
          {weekData.sundayScriptures && weekData.sundayScriptures.length > 0 && (<section className="card"><h3 className="section-heading notes-heading">Key Scriptures:</h3><ul className="scripture-list">{weekData.sundayScriptures.map(s => (<li key={s.ref}><a href={s.url} target="_blank" rel="noopener noreferrer" className="scripture-link">{s.ref}</a><button className={`copy-btn ${copiedId === 'sc-'+s.ref ? 'copied' : ''}`} onClick={() => copyToClipboard(s.ref + ' ' + s.url, 'sc-'+s.ref)} title="Copy reference and link" aria-label="Copy reference and link">{copiedId === 'sc-'+s.ref ? '\u2705' : '\ud83d\udccb'}</button></li>))}</ul></section>)}
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare<button className={`copy-btn ${copiedId === 'sundayComments' ? 'copied' : ''}`} onClick={() => copyToClipboard(sundayComments, 'sundayComments')} title="Copy comments" aria-label="Copy comments">{copiedId === 'sundayComments' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={sundayComments} onChange={setSundayComments} placeholder="Write your prepared comments for the Watchtower study here..." minHeight={180} /></section>
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare (2)<button className={`copy-btn ${copiedId === 'sundayComments2' ? 'copied' : ''}`} onClick={() => copyToClipboard(sundayComments2, 'sundayComments2')} title="Copy comments" aria-label="Copy comments">{copiedId === 'sundayComments2' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={sundayComments2} onChange={setSundayComments2} placeholder="Write more prepared comments here..." minHeight={180} /></section>
          <section className="card"><h3 className="section-heading notes-heading">My Comments to Prepare (3)<button className={`copy-btn ${copiedId === 'sundayComments3' ? 'copied' : ''}`} onClick={() => copyToClipboard(sundayComments3, 'sundayComments3')} title="Copy comments" aria-label="Copy comments">{copiedId === 'sundayComments3' ? '\u2705' : '\ud83d\udccb'}</button></h3><RichNoteEditor value={sundayComments3} onChange={setSundayComments3} placeholder="Write additional prepared comments here..." minHeight={180} /></section>
          <button className="print-btn" onClick={() => window.print()}>Print Meeting Preparation</button>
        </div>
      )}
            {tab === 'todos' && (
  <div className="todo-tab">
    <section className="card">
      <h3 className="section-heading">{"\u2705"} To-Do List</h3>

      <div className="todo-input-row">
        <input
          type="text"
          value={newTodo}
          onChange={e => setNewTodo(e.target.value)}
          placeholder="Add a new task..."
          onKeyDown={e => e.key === 'Enter' && addTodo()}
        />
        <button className="todo-add-btn" onClick={addTodo}>
          Add
        </button>
      </div>

      <div className="todo-options-row">
        <select
          value={newTodoPriority}
          onChange={e => setNewTodoPriority(e.target.value)}
          className="todo-select"
        >
          <option value="high">🔴 High</option>
          <option value="medium">🟡 Medium</option>
          <option value="low">🟢 Low</option>
        </select>

        <select
          value={newTodoCategory}
          onChange={e => setNewTodoCategory(e.target.value)}
          className="todo-select"
        >
          <option value="general">📋 General</option>
          <option value="ministry">📣 Ministry</option>
          <option value="study">📖 Study</option>
          <option value="meeting">🙏 Meeting</option>
          <option value="personal">🎯 Personal</option>
        </select>

        <input
          type="date"
          value={newTodoDue}
          onChange={e => setNewTodoDue(e.target.value)}
          className="todo-date"
        />
      </div>

      <div className="todo-filter-row">
        <button
          className={`todo-filter-btn ${todoFilter === 'all' ? 'active' : ''}`}
          onClick={() => setTodoFilter('all')}
        >
          All ({todos.length})
        </button>
        <button
          className={`todo-filter-btn ${todoFilter === 'active' ? 'active' : ''}`}
          onClick={() => setTodoFilter('active')}
        >
          Active ({todos.length - todoDoneCount})
        </button>
        <button
          className={`todo-filter-btn ${todoFilter === 'done' ? 'active' : ''}`}
          onClick={() => setTodoFilter('done')}
        >
          Done ({todoDoneCount})
        </button>
      </div>
      {todoDoneCount > 0 && (
        <div className="todo-stats">
          <span>{todoDoneCount} completed</span>
          <button className="clear-done-btn" onClick={clearCompleted}>
            Clear completed
          </button>
        </div>
      )}

      {filteredTodos.length === 0 && (
        <p className="todo-empty">
          {todoFilter === 'all'
            ? 'No tasks yet. Add one above!'
            : todoFilter === 'active'
            ? 'All tasks completed!'
            : 'No completed tasks.'}
        </p>
      )}

      {filteredTodos.map(todo => {
        const isEditing = editingTodoId === todo.id
        return (
        <div
          key={todo.id}
          className={`todo-item priority-${todo.priority || 'medium'}`}
        >
          <label className="check-row">
            <input
              type="checkbox"
              checked={todo.done}
              onChange={() => toggleTodo(todo.id, todo.done)}
            />
            {isEditing ? (
              <input
                type="text"
                className="todo-edit-input"
                value={editingTodoText}
                onChange={(e) => setEditingTodoText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitTodoEdit(todo.id)
                  if (e.key === 'Escape') cancelTodoEdit()
                }}
                aria-label="Edit task text"
                autoFocus
              />
            ) : (
              <span className={todo.done ? 'done' : ''}>
                {todo.text}
              </span>
            )}
          </label>

          <div className="todo-meta">
            {todo.due_date && (
                <span
                className={`todo-due ${
                  todo.due_date < todayIso && !todo.done
                    ? 'overdue'
                    : ''
                }`}
              >
                {new Date(todo.due_date + 'T12:00').toLocaleDateString(
                  'en-US',
                  { month: 'short', day: 'numeric' }
                )}
              </span>
            )}

            <span
              className={`todo-priority-badge ${
                todo.priority || 'medium'
              }`}
            >
              {todo.priority === 'high'
                ? '!'
                : todo.priority === 'low'
                ? '○'
                : '●'}
            </span>
          </div>

          {isEditing ? (
            <>
              <button
                className="todo-save-btn"
                onClick={() => submitTodoEdit(todo.id)}
                aria-label="Save task"
              >
                Save
              </button>
              <button
                className="todo-cancel-btn"
                onClick={cancelTodoEdit}
                aria-label="Cancel edit"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                className="todo-edit-btn"
                onClick={() => startTodoEdit(todo)}
                aria-label="Edit task"
              >
                ✏
              </button>

              <button
                className="todo-delete-btn"
                onClick={() => deleteTodo(todo.id)}
                aria-label="Delete task"
              >
                ✕
              </button>
            </>
          )}
        </div>
      )})}
    </section>

    <section className="card">
      <h3 className="section-heading notes-heading">
        ✍️ Journal
        <button
          className={`copy-btn ${
            copiedId === 'todoJournal' ? 'copied' : ''
          }`}
          onClick={() => copyToClipboard(todoJournalText, 'todoJournal')}
          title="Copy journal"
          aria-label="Copy journal"
        >
          {copiedId === 'todoJournal' ? '✅' : '📋'}
        </button>
      </h3>
      <RichNoteEditor
        value={todoJournalText}
        onChange={setTodoJournalText}
        placeholder="Write your thoughts, End of day reflections, notes, and thoughts..."
        minHeight={200}
      />
    </section>
  </div>
)}
      <footer className="footer"><p>Eat Pray Study {"\u00a9"} 2026</p>
      </footer>
    </div>
  )
}
