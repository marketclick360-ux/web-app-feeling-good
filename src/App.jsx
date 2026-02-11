import { useState, useEffect, useCallback, useRef } from 'react'
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

/* Gentle, encouraging affirm messages */
const AFFIRM_MESSAGES = [
  'Even opening this app is a step forward.',
  'Jehovah sees your effort, no matter how small.',
  'You don\'t have to be perfect. Just be present.',
  'A little each day adds up to a lot.',
  'You\'re here. That already matters.',
  'Progress, not perfection.',
  'Every small step counts.',
  'Jehovah is pleased with your desire to draw close.',
  'You\'re doing better than you think.',
  'Be gentle with yourself today.'
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

const SECTION_LABELS = [
  { key: 'treasures', label: '\ud83d\udc8e TREASURES FROM GOD\u2019S WORD', color: '#5b6abf' },
  { key: 'living', label: '\ud83d\udc9a LIVING AS CHRISTIANS', color: '#b5463c' }
]

/* --------- Phase 2: Badges --------- */
const BADGES = [
  { id: 'first_day', icon: '\ud83c\udf31', label: 'First Day', desc: 'Complete your first day', check: s => s.totalDays >= 1 },
  { id: 'week_warrior', icon: '\ud83d\udcaa', label: 'Week Warrior', desc: '7-day streak', check: s => s.bestStreak >= 7 },
  { id: 'two_weeks', icon: '\ud83c\udf1f', label: 'Fortnight', desc: '14-day streak', check: s => s.bestStreak >= 14 },
  { id: 'month_master', icon: '\ud83d\udd25', label: 'Month Master', desc: '30-day streak', check: s => s.bestStreak >= 30 },
  { id: 'double_duty', icon: '\u2728', label: 'Double Duty', desc: 'Both routines in one day', check: s => s.morningStreak >= 1 && s.eveningStreak >= 1 },
  { id: 'perfect_week', icon: '\ud83c\udfc6', label: 'Perfect Week', desc: '90%+ weekly average', check: s => s.weeklyAvg >= 90 },
  { id: 'dedicated', icon: '\ud83d\udc8e', label: 'Dedicated', desc: '60 total days', check: s => s.totalDays >= 60 },
  { id: 'centurion', icon: '\ud83c\udf96\ufe0f', label: 'Centurion', desc: '100 total days', check: s => s.totalDays >= 100 }
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

function ProgressRing({ progress, size = 60, strokeWidth = 6, color }) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const strokeDashoffset = circumference - (progress / 100) * circumference
  const ringColor = color || (progress >= 80 ? '#22c55e' : progress >= 50 ? '#eab308' : '#818cf8')
  return (
    <svg width={size} height={size} className="progress-ring">
      <circle stroke="rgba(255,255,255,0.08)" fill="transparent" strokeWidth={strokeWidth} r={radius} cx={size/2} cy={size/2} />
      <circle className="progress-ring-circle" stroke={ringColor} fill="transparent" strokeWidth={strokeWidth} strokeDasharray={`${circumference} ${circumference}`} style={{ strokeDashoffset, transform: 'rotate(-90deg)', transformOrigin: '50% 50%', strokeLinecap: 'round' }} r={radius} cx={size/2} cy={size/2} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" fill="#e2e8f0" fontSize="0.8rem" fontWeight="700">{Math.round(progress)}%</text>
    </svg>
  )
}

/* --------- Streak helpers (enhanced for Phase 2) --------- */
async function computeStreak() {
  const today = new Date()
  const dates = []
  for (let i = 0; i < 120; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    dates.push(toISO(d))
  }
  const { data } = await supabase
    .from('journal_entries')
    .select('entry_date, morning_checks, evening_checks')
    .in('entry_date', dates)
    .order('entry_date', { ascending: false })
  if (!data) return { morningStreak: 0, eveningStreak: 0, bestStreak: 0, totalDays: 0, last7: [], weeklyAvg: 0, challengeAvg: 0 }
  const byDate = {}
  data.forEach(row => { byDate[row.entry_date] = row })
  let morningStreak = 0, eveningStreak = 0, mCounting = true, eCounting = true, totalDays = 0
  const last7 = []
  let weeklyTotal = 0, challengeTotal = 0, challengeDays = 0
  for (let i = 0; i < dates.length; i++) {
    const dateKey = dates[i]
    const row = byDate[dateKey]
    const mChecks = row && row.morning_checks ? Object.values(row.morning_checks).filter(Boolean).length : 0
    const eChecks = row && row.evening_checks ? Object.values(row.evening_checks).filter(Boolean).length : 0
    const mPct = Math.round((mChecks / 6) * 100)
    const ePct = Math.round((eChecks / 6) * 100)
    const dayAvg = Math.round((mPct + ePct) / 2)
    if (i < 7) { last7.push({ date: dateKey, morningPct: mPct, eveningPct: ePct }); weeklyTotal += dayAvg }
    if (mPct > 0 || ePct > 0) { challengeTotal += dayAvg; challengeDays++ }
    if (mPct >= 80 && mCounting) morningStreak++; else mCounting = false
    if (ePct >= 80 && eCounting) eveningStreak++; else eCounting = false
    if (mPct > 0 || ePct > 0) totalDays++
  }
  const bestStreak = Math.max(morningStreak, eveningStreak)
  const weeklyAvg = last7.length > 0 ? Math.round(weeklyTotal / last7.length) : 0
  const challengeAvg = challengeDays > 0 ? Math.round(challengeTotal / challengeDays) : 0
  return { morningStreak, eveningStreak, bestStreak, totalDays, last7, weeklyAvg, challengeAvg }
}

/* --------- Mini Week Chart --------- */
function WeekChart({ data, type }) {
  const days = ['S','M','T','W','T','F','S']
  return (
    <div className="week-chart">
      {data.map((d, i) => {
        const pct = type === 'morning' ? d.morningPct : d.eveningPct
        const dayDate = new Date(d.date + 'T12:00')
        const dayLabel = days[dayDate.getDay()]
        return (
          <div className="week-chart-bar" key={i}>
            <div className="week-chart-fill" style={{ height: `${Math.max(pct, 4)}%`, background: pct >= 80 ? '#22c55e' : pct >= 50 ? '#eab308' : 'rgba(129,140,248,0.5)' }} />
            <span className="week-chart-label">{dayLabel}</span>
          </div>
        )
      }).reverse()}
    </div>
  )
}

/* --------- Phase 3: Confetti Celebration --------- */
function Confetti({ active }) {
  const canvasRef = useRef(null)
  useEffect(() => {
    if (!active || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    const particles = []
    const colors = ['#818cf8','#c084fc','#f472b6','#22c55e','#eab308','#fbbf24','#a78bfa']
    for (let i = 0; i < 80; i++) {
      particles.push({ x: Math.random() * canvas.width, y: -20 - Math.random() * 200, w: 4 + Math.random() * 6, h: 8 + Math.random() * 8, color: colors[Math.floor(Math.random() * colors.length)], vx: (Math.random() - 0.5) * 3, vy: 2 + Math.random() * 4, rot: Math.random() * 360, rotSpeed: (Math.random() - 0.5) * 10, opacity: 1 })
    }
    let frame
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      let alive = false
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy; p.vy += 0.08; p.rot += p.rotSpeed
        if (p.y > canvas.height - 100) p.opacity -= 0.02
        if (p.opacity <= 0) return
        alive = true
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot * Math.PI / 180)
        ctx.globalAlpha = Math.max(0, p.opacity); ctx.fillStyle = p.color
        ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h); ctx.restore()
      })
      if (alive) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [active])
  if (!active) return null
  return <canvas ref={canvasRef} className="confetti-canvas" />
}

/* ========= MAIN APP ========= */
export default function App() {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const [tab, setTab] = useState('today')
  const [morningChecks, setMorningChecks] = useState({})
  const [eveningChecks, setEveningChecks] = useState({})
  const [midweekChecks, setMidweekChecks] = useState({})
  const [sundayChecks, setSundayChecks] = useState({})
  const [treasuresComments, setTreasuresComments] = useState('')
  const [todos, setTodos] = useState([])
  const [newTodo, setNewTodo] = useState('')
  const [todoPriority, setTodoPriority] = useState('medium')
  const [todoDue, setTodoDue] = useState('')
  const [todoFilter, setTodoFilter] = useState('all')
  const [dailyText, setDailyText] = useState(null)
  const [streak, setStreak] = useState({ morningStreak: 0, eveningStreak: 0, bestStreak: 0, totalDays: 0, last7: [], weeklyAvg: 0, challengeAvg: 0 })
  const [showConfetti, setShowConfetti] = useState(false)
  const [tabFade, setTabFade] = useState('tab-fade-in')
  const [copied, setCopied] = useState({})
  const [routineDate, setRoutineDate] = useState(() => todayStr())
  const [affirmMsg] = useState(() => AFFIRM_MESSAGES[Math.floor(Math.random() * AFFIRM_MESSAGES.length)])
  const prevTab = useRef(tab)

  const weekKey = toISO(weekStart)
  const week = getWeekData(weekKey)

  /* --- Tab transition --- */
  const switchTab = useCallback((t) => {
    if (t === tab) return
    setTabFade('tab-fade-out')
    setTimeout(() => { setTab(t); setTabFade('tab-fade-in') }, 150)
  }, [tab])

  useEffect(() => { prevTab.current = tab }, [tab])

  /* --- Load daily text --- */
  useEffect(() => {
    fetch('https://daily-text-proxy.vercel.app/api/daily-text')
      .then(r => r.json()).then(setDailyText).catch(() => {})
  }, [])

  /* --- Load data from Supabase --- */
  const loadDay = useCallback(async (dateStr) => {
    const { data } = await supabase
      .from('journal_entries')
      .select('*')
      .eq('entry_date', dateStr)
      .maybeSingle()
    if (data) {
      setMorningChecks(data.morning_checks || {})
      setEveningChecks(data.evening_checks || {})
    } else {
      setMorningChecks({})
      setEveningChecks({})
    }
  }, [])

  useEffect(() => { loadDay(routineDate) }, [routineDate, loadDay])

  const loadWeek = useCallback(async () => {
    const key = toISO(weekStart)
    const { data } = await supabase
      .from('journal_entries')
      .select('*')
      .eq('entry_date', key)
      .maybeSingle()
    if (data) {
      setMidweekChecks(data.midweek_checks || {})
      setSundayChecks(data.sunday_checks || {})
      setTreasuresComments(data.treasures_comments || '')
    } else {
      setMidweekChecks({})
      setSundayChecks({})
      setTreasuresComments('')
    }
  }, [weekStart])

  useEffect(() => { loadWeek() }, [loadWeek])

  const loadTodos = useCallback(async () => {
    const { data } = await supabase.from('todos').select('*').order('created_at', { ascending: false })
    if (data) setTodos(data)
  }, [])

  useEffect(() => { loadTodos() }, [loadTodos])

  /* --- Streak --- */
  const refreshStreak = useCallback(async () => {
    const s = await computeStreak()
    setStreak(s)
  }, [])

  useEffect(() => { refreshStreak() }, [refreshStreak])

  /* --- Save helpers --- */
  const saveDay = useCallback(async (mc, ec) => {
    const payload = { entry_date: routineDate, morning_checks: mc, evening_checks: ec }
    await supabase.from('journal_entries').upsert(payload, { onConflict: 'entry_date' })
    refreshStreak()
  }, [routineDate, refreshStreak])

  const saveWeek = useCallback(async (mw, su, tc) => {
    const key = toISO(weekStart)
    const payload = { entry_date: key, midweek_checks: mw, sunday_checks: su, treasures_comments: tc }
    await supabase.from('journal_entries').upsert(payload, { onConflict: 'entry_date' })
  }, [weekStart])

  /* --- Toggle handlers --- */
  const toggleMorning = (key) => {
    const next = { ...morningChecks, [key]: !morningChecks[key] }
    setMorningChecks(next)
    saveDay(next, eveningChecks)
    const doneCount = Object.values(next).filter(Boolean).length
    if (doneCount === MORNING_ROUTINE.length) { setShowConfetti(true); setTimeout(() => setShowConfetti(false), 3000) }
  }

  const toggleEvening = (key) => {
    const next = { ...eveningChecks, [key]: !eveningChecks[key] }
    setEveningChecks(next)
    saveDay(morningChecks, next)
    const doneCount = Object.values(next).filter(Boolean).length
    if (doneCount === EVENING_ROUTINE.length) { setShowConfetti(true); setTimeout(() => setShowConfetti(false), 3000) }
  }

  const toggleMidweek = (id) => {
    const next = { ...midweekChecks, [id]: !midweekChecks[id] }
    setMidweekChecks(next)
    saveWeek(next, sundayChecks, treasuresComments)
  }

  const toggleSunday = (key) => {
    const next = { ...sundayChecks, [key]: !sundayChecks[key] }
    setSundayChecks(next)
    saveWeek(midweekChecks, next, treasuresComments)
  }

  const handleCommentsChange = (val) => {
    setTreasuresComments(val)
    saveWeek(midweekChecks, sundayChecks, val)
  }

  /* --- Copy to clipboard --- */
  const copyText = (text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(p => ({ ...p, [id]: true }))
      setTimeout(() => setCopied(p => ({ ...p, [id]: false })), 1500)
    })
  }

  /* --- Todo handlers --- */
  const addTodo = async () => {
    if (!newTodo.trim()) return
    const item = { text: newTodo.trim(), done: false, priority: todoPriority, due_date: todoDue || null }
    const { data } = await supabase.from('todos').insert(item).select()
    if (data) setTodos([data[0], ...todos])
    setNewTodo(''); setTodoPriority('medium'); setTodoDue('')
  }

  const toggleTodo = async (id) => {
    const t = todos.find(x => x.id === id)
    if (!t) return
    await supabase.from('todos').update({ done: !t.done }).eq('id', id)
    setTodos(todos.map(x => x.id === id ? { ...x, done: !x.done } : x))
  }

  const deleteTodo = async (id) => {
    await supabase.from('todos').delete().eq('id', id)
    setTodos(todos.filter(x => x.id !== id))
  }

  const clearDone = async () => {
    const doneIds = todos.filter(t => t.done).map(t => t.id)
    if (!doneIds.length) return
    await supabase.from('todos').delete().in('id', doneIds)
    setTodos(todos.filter(t => !t.done))
  }

  /* --- Computed --- */
  const morningDone = Object.values(morningChecks).filter(Boolean).length
  const eveningDone = Object.values(eveningChecks).filter(Boolean).length
  const morningPct = Math.round((morningDone / MORNING_ROUTINE.length) * 100)
  const eveningPct = Math.round((eveningDone / EVENING_ROUTINE.length) * 100)
  const isToday = routineDate === todayStr()

  /* Day navigation */
  const prevDay = () => {
    const d = new Date(routineDate + 'T12:00')
    d.setDate(d.getDate() - 1)
    setRoutineDate(toISO(d))
  }
  const nextDay = () => {
    const d = new Date(routineDate + 'T12:00')
    d.setDate(d.getDate() + 1)
    setRoutineDate(toISO(d))
  }
  const goToday = () => setRoutineDate(todayStr())

  /* Filtered todos */
  const filteredTodos = todos.filter(t => {
    if (todoFilter === 'active') return !t.done
    if (todoFilter === 'done') return t.done
    return true
  })
  const todoStats = { total: todos.length, done: todos.filter(t => t.done).length }

  const displayDate = new Date(routineDate + 'T12:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  /* ========= RENDER ========= */
  return (
    <div className="app">
      <Confetti active={showConfetti} />

      {/* --- Header: Warm, identity-focused --- */}
      <header className="header">
        <h1>Spiritual Growth Companion</h1>
        <div className="week-label">{formatRange(weekStart)}</div>
        <div className="week-nav">
          <button onClick={() => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }}>← Prev</button>
          <button onClick={() => setWeekStart(mondayOf(new Date()))}>This Week</button>
          <button onClick={() => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }}>Next →</button>
        </div>
      </header>

      {/* --- Tab Content --- */}
      <div className={`tab-content ${tabFade}`}>

        {/* ===== TODAY TAB - Warm Welcome ===== */}
        {tab === 'today' && (
          <div className="today-tab">
            {/* Warm greeting card */}
            <div className="card greeting-card">
              <div className="greeting-title">{getGreeting()}</div>
              <p className="affirm-message">{affirmMsg}</p>
              <div className="greeting-date">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</div>
            </div>

            {/* Gentle journey card - NOT a harsh streak */}
            {streak.totalDays > 0 && (
              <div className="card journey-card">
                <h3 className="journey-title">\ud83c\udf31 Your Journey</h3>
                <p className="journey-text">
                  You've shown up <strong>{streak.totalDays} {streak.totalDays === 1 ? 'day' : 'days'}</strong> so far.
                  {streak.bestStreak > 1 && ` Your longest rhythm was ${streak.bestStreak} days in a row.`}
                  {streak.totalDays === 0 && ' Today could be day one.'}
                </p>
                {streak.last7.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '6px' }}>This week</div>
                    <WeekChart data={streak.last7} type="morning" />
                  </div>
                )}
              </div>
            )}

            {/* Daily Text */}
            <div className="card daily-text-card">
              <h3 className="section-heading">\ud83d\udcd6 Daily Text</h3>
              {dailyText ? (
                <div className="daily-text-content">
                  <div className="daily-text-date">{dailyText.date}</div>
                  <div className="daily-text-scripture" dangerouslySetInnerHTML={{ __html: dailyText.scripture }} />
                  <div className="daily-text-ref">{dailyText.reference}</div>
                  <div className="daily-text-comment" dangerouslySetInnerHTML={{ __html: dailyText.comment }} />
                  <a className="workbook-link" href="https://wol.jw.org/en/wol/h/r1/lp-e" target="_blank" rel="noreferrer">Read on WOL \u2192</a>
                </div>
              ) : <p className="daily-text-loading">Loading daily text...</p>}
            </div>

            {/* Encouragement */}
            <div className="card encouragement-card">
              <p className="encouragement-verse">\u201cFor I well know the thoughts that I am thinking toward you,\u201d declares Jehovah, \u201cthoughts of peace, and not of calamity, to give you a future and a hope.\u201d</p>
              <p className="encouragement-ref">\u2014 Jeremiah 29:11</p>
            </div>

            {/* Quick access links */}
            <div className="card quick-links-card">
              <h3 className="section-heading">Quick Access</h3>
              <div className="quick-links-grid">
                <a className="quick-link-btn" href={week.workbookUrl} target="_blank" rel="noreferrer">\ud83d\udcd3 Workbook</a>
                <button className="quick-link-btn" onClick={() => switchTab('morning')}>\u2600\ufe0f Morning</button>
                <button className="quick-link-btn" onClick={() => switchTab('evening')}>\ud83c\udf19 Evening</button>
                <button className="quick-link-btn" onClick={() => switchTab('midweek')}>\ud83d\udcda Midweek</button>
              </div>
            </div>
          </div>
        )}

        {/* ===== MORNING TAB ===== */}
        {tab === 'morning' && (
          <div>
            <div className="day-nav">
              <button className="day-nav-btn" onClick={prevDay}>\u2190</button>
              <span className="routine-date">{displayDate}</span>
              <button className="day-nav-btn" onClick={nextDay}>\u2192</button>
              {!isToday && <button className="today-btn" onClick={goToday}>Today</button>}
            </div>

            {/* Gentle encouragement instead of pressure */}
            <div className="card">
              <div className="routine-verse">\u201cStart your day by drawing close to Jehovah. Even a few minutes matter.\u201d</div>
              <h3 className="section-heading morning-heading">\u2600\ufe0f Morning Routine</h3>

              {/* Gentle progress - not demanding */}
              {morningDone > 0 && (
                <div className="streak-summary-card">
                  <div className="streak-progress-row">
                    <ProgressRing progress={morningPct} size={50} />
                    <div className="streak-info">
                      <div className="streak-message">{morningDone === MORNING_ROUTINE.length ? '\u2728 Beautiful! All done.' : `${morningDone} of ${MORNING_ROUTINE.length} \u2014 every bit counts`}</div>
                    </div>
                  </div>
                </div>
              )}

              {MORNING_ROUTINE.map(item => (
                <div className={`check-row ${morningChecks[item.key] ? 'check-row-done' : ''}`} key={item.key} onClick={() => toggleMorning(item.key)}>
                  <input type="checkbox" checked={!!morningChecks[item.key]} readOnly />
                  <span className={morningChecks[item.key] ? 'done' : ''}>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== EVENING TAB ===== */}
        {tab === 'evening' && (
          <div>
            <div className="day-nav">
              <button className="day-nav-btn" onClick={prevDay}>\u2190</button>
              <span className="routine-date">{displayDate}</span>
              <button className="day-nav-btn" onClick={nextDay}>\u2192</button>
              {!isToday && <button className="today-btn" onClick={goToday}>Today</button>}
            </div>

            <div className="card">
              <div className="routine-verse">\u201cEnd your day in peace. Reflect on Jehovah's goodness.\u201d</div>
              <h3 className="section-heading evening-heading">\ud83c\udf19 Evening Routine</h3>

              {eveningDone > 0 && (
                <div className="streak-summary-card">
                  <div className="streak-progress-row">
                    <ProgressRing progress={eveningPct} size={50} />
                    <div className="streak-info">
                      <div className="streak-message">{eveningDone === EVENING_ROUTINE.length ? '\u2728 Wonderful evening!' : `${eveningDone} of ${EVENING_ROUTINE.length} \u2014 well done`}</div>
                    </div>
                  </div>
                </div>
              )}

              {EVENING_ROUTINE.map(item => (
                <div className={`check-row ${eveningChecks[item.key] ? 'check-row-done' : ''}`} key={item.key} onClick={() => toggleEvening(item.key)}>
                  <input type="checkbox" checked={!!eveningChecks[item.key]} readOnly />
                  <span className={eveningChecks[item.key] ? 'done' : ''}>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== MIDWEEK TAB ===== */}
        {tab === 'midweek' && (
          <div>
            <div className="card meeting-card">
              <a href={week.workbookUrl} target="_blank" rel="noreferrer" className="meeting-title-link">
                <h2>{week.theme || 'Midweek Meeting'}</h2>
              </a>
              <p className="meeting-subtitle">{week.bibleReading && `Bible Reading: ${week.bibleReading}`} {week.song && `\u2022 ${week.song}`}</p>
              <a href={week.workbookUrl} target="_blank" rel="noreferrer" className="workbook-btn">Open Meeting Workbook</a>
            </div>

            {SECTION_LABELS.map(sec => (
              <div key={sec.key}>
                <h3 className="section-heading" style={{ borderLeftColor: sec.color }}>{sec.label}
                  <button className={`copy-btn ${copied['sec_'+sec.key] ? 'copied' : ''}`} onClick={() => copyText(week.sections[sec.key].map(p => p.text).join('\n'), 'sec_'+sec.key)}>{copied['sec_'+sec.key] ? '\u2713' : '\ud83d\udccb'}</button>
                </h3>
                {week.sections[sec.key].map(part => (
                  <div className="meeting-part-item" key={part.id}>
                    <label className="check-row" onClick={() => toggleMidweek(part.id)}>
                      <input type="checkbox" checked={!!midweekChecks[part.id]} readOnly />
                      <span className={midweekChecks[part.id] ? 'done' : ''}>{part.text}</span>
                    </label>
                    <button className={`copy-btn ${copied[part.id] ? 'copied' : ''}`} onClick={() => copyText(part.text, part.id)}>{copied[part.id] ? '\u2713' : '\ud83d\udccb'}</button>
                  </div>
                ))}
              </div>
            ))}

            {/* Treasures comments */}
            <div className="card">
              <div className="treasures-comments">
                <div className="treasures-comments-title">\ud83d\udcdd My Notes
                  <button className={`copy-btn ${copied['tc'] ? 'copied' : ''}`} onClick={() => copyText(treasuresComments, 'tc')}>{copied['tc'] ? '\u2713' : '\ud83d\udccb'}</button>
                </div>
                <textarea rows={4} value={treasuresComments} onChange={e => handleCommentsChange(e.target.value)} placeholder="Jot down thoughts, comments, or applications..." />
              </div>
            </div>
          </div>
        )}

        {/* ===== SUNDAY TAB ===== */}
        {tab === 'sunday' && (
          <div>
            <div className="card meeting-card">
              <h2>\ud83d\udcd6 Sunday Meeting Prep</h2>
              {week.sundayArticle && (
                <div className="sunday-article-box">
                  <p><strong>Study Article:</strong> {week.sundayArticle}</p>
                </div>
              )}
            </div>

            {/* Sunday scriptures */}
            {week.sundayScriptures && week.sundayScriptures.length > 0 && (
              <div className="card">
                <h3 className="section-heading sunday-heading">Key Scriptures</h3>
                <ul className="scripture-list">
                  {week.sundayScriptures.map((s, i) => (
                    <li key={i}>
                      <a href={s.url} target="_blank" rel="noreferrer" className="scripture-link">{s.ref}</a>
                      <button className={`copy-btn ${copied['ss'+i] ? 'copied' : ''}`} onClick={() => copyText(s.ref, 'ss'+i)}>{copied['ss'+i] ? '\u2713' : '\ud83d\udccb'}</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Sunday checklist */}
            <div className="card">
              <h3 className="section-heading sunday-heading">\u2705 Preparation Checklist</h3>
              {SUNDAY_CHECKLIST.map(item => (
                <div className={`check-row ${sundayChecks[item.key] ? 'check-row-done' : ''}`} key={item.key} onClick={() => toggleSunday(item.key)}>
                  <input type="checkbox" checked={!!sundayChecks[item.key]} readOnly />
                  <span className={sundayChecks[item.key] ? 'done' : ''}>{item.label}</span>
                </div>
              ))}
            </div>

            <button className="print-btn" onClick={() => window.print()}>\ud83d\udda8\ufe0f Print Sunday Notes</button>
          </div>
        )}

        {/* ===== TODO TAB ===== */}
        {tab === 'todos' && (
          <div>
            <div className="card">
              <h3 className="section-heading notes-heading">\ud83d\udcdd Spiritual Goals</h3>
              <div className="todo-input-row">
                <input type="text" value={newTodo} onChange={e => setNewTodo(e.target.value)} placeholder="Add a goal or task..." onKeyDown={e => e.key === 'Enter' && addTodo()} />
                <button className="todo-add-btn" onClick={addTodo}>Add</button>
              </div>
              <div className="todo-options-row">
                <select className="todo-select" value={todoPriority} onChange={e => setTodoPriority(e.target.value)}>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <input type="date" className="todo-date" value={todoDue} onChange={e => setTodoDue(e.target.value)} />
              </div>

              {todoStats.total > 0 && (
                <div className="todo-stats">
                  <span>{todoStats.done} of {todoStats.total} done</span>
                  {todoStats.done > 0 && <button className="clear-done-btn" onClick={clearDone}>Clear done</button>}
                </div>
              )}

              <div className="todo-filter-row">
                {['all','active','done'].map(f => (
                  <button key={f} className={`todo-filter-btn ${todoFilter === f ? 'active' : ''}`} onClick={() => setTodoFilter(f)}>{f.charAt(0).toUpperCase() + f.slice(1)}</button>
                ))}
              </div>

              {filteredTodos.length === 0 && <p className="todo-empty">No goals yet. Start small!</p>}
              {filteredTodos.map(t => (
                <div className={`todo-item priority-${t.priority || 'medium'}`} key={t.id}>
                  <div className="check-row" onClick={() => toggleTodo(t.id)}>
                    <input type="checkbox" checked={!!t.done} readOnly />
                    <span className={t.done ? 'done' : ''}>{t.text}</span>
                  </div>
                  <div className="todo-meta">
                    {t.priority && <span className={`todo-priority-badge ${t.priority}`}>{t.priority.toUpperCase()}</span>}
                    {t.due_date && <span className={`todo-due ${new Date(t.due_date) < new Date() && !t.done ? 'overdue' : ''}`}>{t.due_date}</span>}
                  </div>
                  <button className="todo-delete-btn" onClick={() => deleteTodo(t.id)}>\u00d7</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== GROWTH TAB - Identity-focused ===== */}
        {tab === 'growth' && (
          <div>
            {/* Weekly summary - gentle, not competitive */}
            <div className="card">
              <h3 className="section-heading">\ud83c\udf3f This Week</h3>
              <div className="weekly-summary-grid">
                <div className="weekly-summary-item">
                  <span className="weekly-stat-big">{streak.totalDays}</span>
                  <span className="weekly-summary-label">Days Active</span>
                </div>
                <div className="weekly-summary-item">
                  <span className="weekly-stat-big">{streak.bestStreak}</span>
                  <span className="weekly-summary-label">Best Rhythm</span>
                </div>
                <div className="weekly-summary-item">
                  <span className="weekly-stat-big">{streak.weeklyAvg}%</span>
                  <span className="weekly-summary-label">This Week</span>
                </div>
              </div>
            </div>

            {/* 21-day challenge - reframed as gentle rhythm builder */}
            <div className="card">
              <h3 className="section-heading">\ud83c\udf31 21-Day Rhythm Builder</h3>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '12px' }}>Building a new habit takes time. You're {Math.min(streak.totalDays, 21)} days into your rhythm.</p>
              <div className="challenge-bar-wrap">
                <div className="challenge-bar-bg">
                  <div className="challenge-bar-fill" style={{ width: `${Math.min((streak.totalDays / 21) * 100, 100)}%`, background: streak.totalDays >= 21 ? 'linear-gradient(90deg, #22c55e, #16a34a)' : 'linear-gradient(90deg, #818cf8, #c084fc)' }} />
                </div>
                <div className="challenge-bar-labels">
                  <span>Day 1</span><span>Day 7</span><span>Day 14</span><span>Day 21</span>
                </div>
              </div>
              {streak.totalDays >= 21 && <p className="challenge-goal">\u2728 You've built a rhythm! Keep going.</p>}
            </div>

            {/* Badges */}
            <div className="card">
              <h3 className="section-heading">\ud83c\udfc5 Milestones</h3>
              <div className="badges-grid">
                {BADGES.map(b => {
                  const unlocked = b.check(streak)
                  return (
                    <div className={`badge-item ${unlocked ? 'unlocked' : 'locked'}`} key={b.id}>
                      <span className="badge-icon">{b.icon}</span>
                      <span className="badge-label">{b.label}</span>
                      <span className="badge-desc">{b.desc}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

      </div>{/* end tab-content */}

      {/* --- Footer --- */}
      <div className="footer">Spiritual Growth Companion</div>

      {/* --- Tab Bar --- */}
      <nav className="tab-row">
        {[
          { id: 'today', icon: '\ud83c\udfe0', name: 'Today' },
          { id: 'morning', icon: '\u2600\ufe0f', name: 'Morning' },
          { id: 'evening', icon: '\ud83c\udf19', name: 'Evening' },
          { id: 'midweek', icon: '\ud83d\udcda', name: 'Midweek' },
          { id: 'sunday', icon: '\ud83d\udcd6', name: 'Sunday' },
          { id: 'todos', icon: '\ud83d\udcdd', name: 'Goals' },
        { id: 'calendar', icon: '\ud83d\udcc5', name: 'Calendar' },
          { id: 'growth', icon: '\ud83c\udf31', name: 'Growth' }
        ].map(t => (
          <button key={t.id} className={`tab ${tab === t.id ? 'active' : ''}`} onClick={() => switchTab(t.id)}>
            <span className="tab-icon">{t.icon}</span>
            <span className="tab-name">{t.name}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
