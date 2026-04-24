# Claude Code — Project Preferences

## Clarification Before Action

Before starting any non-trivial task, ask **3–4 clarifying questions** to understand context, goals, and constraints. Use interactive checkbox Q&A where the interface supports it. Once enough context is gathered, respond fully without further unnecessary questions. The goal is a better response that covers edge cases the user may not have anticipated.

## Improve & Suggest

While working, briefly note opportunities for automation, improvement, or repeatability (1–2 sentences, only when relevant). If a task is a good candidate for a Claude Skill, say so — and remind the user to update their Skills or preferences based on usage patterns.

## File & Output Preferences

Default to **Markdown (.md)** for any file output unless the request clearly calls for another format (docx, xlsx, pptx, etc.). When no file is needed, respond directly in chat.

---

## Project Context

**App name:** Eat Pray Study (Pioneer Spiritual Growth Tracker)
**Audience:** Jehovah's Witnesses serving as full-time volunteer ministers (pioneers)

### Stack
- React 18 + Vite (JSX, no routing library — tab-based SPA)
- Supabase (Postgres + OTP email auth, no passwords)
- Vercel (serverless functions under `/api/`, cron job for keep-alive)
- Capacitor 6 (iOS wrapper pointing to hosted Vercel URL)
- PWA (service worker + manifest)
- Plain CSS — glassmorphism design system (dark navy `#0a0a1a`, `backdrop-filter: blur`)

### Key files
| File | Purpose |
|------|---------|
| `src/App.jsx` | Main component (~950 lines, all tabs inline) |
| `src/App.css` | All styles (~2800 lines, single flat file) |
| `src/AuthGate.jsx` | OTP email auth wrapper |
| `src/RichNoteEditor.jsx` | Custom `contentEditable` rich text editor |
| `api/meeting-data.js` | Weekly meeting data (hardcoded + fallback) |
| `api/encouragement.js` | Daily rotating scripture (58-entry pool) |
| `api/daily-text.js` | Returns WOL link for today's daily text |

### Tabs
| Tab | Key |
|-----|-----|
| Morning routine + journal | `morning` |
| Midweek meeting prep | `prep` |
| Sunday meeting prep | `sunday` |
| To-do list + journal | `todos` |

### Data persistence
- `journal_entries` table — daily morning/evening checks, goals, journal text
- `weeks` table — weekly meeting prep notes and checks
- `todo_items` table — per-user task list
- All saves debounced 800 ms, upsert on conflict

### Design tokens
- Primary accent: `#818cf8` (indigo)
- Morning accent: `#fbbf24` (amber)
- Evening accent: `#818cf8` (indigo/violet)
- Sunday accent: `#c084fc` (purple)
- Glass card: `rgba(255,255,255,0.05)` + `backdrop-filter: blur(40px)`
- Border radius: 22px (cards), 14px (inputs/buttons), 16px (items)

### Known technical debt
- `App.jsx` is monolithic (~950 lines, ~30 `useState` calls) — avoid making it larger without decomposing
- `App.css` is a single flat file — append new rules at the bottom to avoid conflicts
- Meeting data is hardcoded for a fixed date range; fallback logic handles unknown weeks
- `/api/daily-text.js` returns only a URL, not the actual scripture text

### Development branch
All changes go to: `claude/enhance-app-experience-g3mat`
