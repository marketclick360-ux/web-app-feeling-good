import { useState, useMemo, useEffect, useCallback } from 'react'
import { extractScriptures, groupScriptures } from './scriptureParser'

/* Watchtower Study tab: paste an article, get every scripture as a tappable
 * link to the official NWT on the Watchtower Online Library (wol.jw.org).
 * Article text is kept in localStorage so it survives a reload / offline use. */

const STORAGE_KEY = 'eps-wt-study'

export default function WatchtowerStudy() {
  const [article, setArticle] = useState('')
  const [title, setTitle] = useState('')
  const [copiedId, setCopiedId] = useState(null)

  // Restore last pasted article.
  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
      if (saved.article) setArticle(saved.article)
      if (saved.title) setTitle(saved.title)
    } catch { /* ignore corrupt storage */ }
  }, [])

  // Persist on change.
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ article, title }))
    } catch { /* storage full / disabled */ }
  }, [article, title])

  const refs = useMemo(() => extractScriptures(article), [article])
  const { read, related } = useMemo(() => groupScriptures(refs), [refs])

  // Use the first non-empty line as an auto-detected title if the user hasn't set one.
  const detectedTitle = useMemo(() => {
    if (title.trim()) return title.trim()
    const firstLine = (article.split('\n').find(l => l.trim()) || '').trim()
    return firstLine.slice(0, 120)
  }, [title, article])

  const copy = useCallback((text, id) => {
    const done = () => { setCopiedId(id); setTimeout(() => setCopiedId(c => (c === id ? null : c)), 1500) }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(done)
    } else {
      done()
    }
  }, [])

  const copyAll = useCallback(() => {
    if (!refs.length) return
    const header = detectedTitle ? `${detectedTitle}\n\n` : ''
    const body = refs.map(r => `${r.ref}${r.isRead ? ' (Read)' : ''}\n${r.url}`).join('\n\n')
    copy(header + body, 'all')
  }, [refs, detectedTitle, copy])

  const clearAll = useCallback(() => {
    setArticle('')
    setTitle('')
  }, [])

  const renderItem = (r) => (
    <li key={r.ref} className="wt-study-item">
      <a href={r.url} target="_blank" rel="noopener noreferrer" className="scripture-link">{r.ref}</a>
      <button
        className={`copy-btn ${copiedId === r.ref ? 'copied' : ''}`}
        onClick={() => copy(`${r.ref} ${r.url}`, r.ref)}
        title="Copy reference and link"
        aria-label={`Copy ${r.ref}`}
      >{copiedId === r.ref ? '✅' : '📋'}</button>
    </li>
  )

  return (
    <div className="study-tab">
      <section className="card">
        <h3 className="section-heading study-heading">{'📖'} Watchtower Study</h3>
        <p className="study-intro">
          Paste this week&rsquo;s Watchtower article below. Every scripture &mdash; both the
          &ldquo;Read&rdquo; texts and the related references &mdash; is pulled out and linked to the
          official New World Translation on the Watchtower Online Library.
        </p>
        <input
          type="text"
          className="study-title-input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Article title (optional — auto-detected from first line)"
          aria-label="Article title"
        />
        <textarea
          className="study-textarea"
          value={article}
          onChange={e => setArticle(e.target.value)}
          placeholder="Paste the full Watchtower article here… scriptures are found automatically as you paste."
          aria-label="Watchtower article text"
          rows={10}
        />
        <div className="study-actions">
          <span className="study-count">{refs.length} scripture{refs.length === 1 ? '' : 's'} found</span>
          <div className="study-action-btns">
            <button className="today-btn" onClick={copyAll} disabled={!refs.length}>
              {copiedId === 'all' ? '✅ Copied' : '📋 Copy all'}
            </button>
            <button className="study-clear-btn" onClick={clearAll} disabled={!article}>Clear</button>
          </div>
        </div>
      </section>

      {refs.length === 0 && article.trim() && (
        <section className="card">
          <p className="study-empty">No scriptures detected yet. Make sure the article text (with references like &ldquo;Matthew 19:6&rdquo;) is pasted above.</p>
        </section>
      )}

      {read.length > 0 && (
        <section className="card">
          <h3 className="section-heading study-heading">{'⭐'} &ldquo;Read&rdquo; Scriptures <span className="study-tag">{read.length}</span></h3>
          <p className="study-sub">The key texts the article asks you to read aloud.</p>
          <ul className="scripture-list wt-study-list">{read.map(renderItem)}</ul>
        </section>
      )}

      {related.length > 0 && (
        <section className="card">
          <h3 className="section-heading study-heading">{'🔗'} Related Scriptures <span className="study-tag">{related.length}</span></h3>
          <p className="study-sub">Every other scripture cited in the article.</p>
          <ul className="scripture-list wt-study-list">{related.map(renderItem)}</ul>
        </section>
      )}

      {refs.length > 0 && (
        <button className="print-btn" onClick={() => window.print()}>Print scripture list</button>
      )}
    </div>
  )
}
