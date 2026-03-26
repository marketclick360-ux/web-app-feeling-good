import { useRef, useEffect, useCallback, useState } from 'react'

const FONT_COLORS = [
  { color: '#e2e8f0', label: 'Default' },
  { color: '#fbbf24', label: 'Yellow' },
  { color: '#4ade80', label: 'Green' },
  { color: '#f472b6', label: 'Pink' },
  { color: '#22d3ee', label: 'Cyan' },
  { color: '#fb923c', label: 'Orange' },
]

export default function RichNoteEditor({ value, onChange, placeholder = 'Write your notes...', minHeight = 120 }) {
  const editorRef = useRef(null)
  const isInternalChange = useRef(false)
  const [expandedImg, setExpandedImg] = useState(null)
  const [height, setHeight] = useState(minHeight)
  const resizingRef = useRef(false)
  const startYRef = useRef(0)
  const startHeightRef = useRef(minHeight)
  const [showColors, setShowColors] = useState(false)

  useEffect(() => {
    if (isInternalChange.current) { isInternalChange.current = false; return }
    const el = editorRef.current
    if (el && el.innerHTML !== (value || '')) el.innerHTML = value || ''
  }, [value])

  useEffect(() => {
    const onMove = (e) => {
      if (!resizingRef.current) return
      const clientY = e.touches ? e.touches[0].clientY : e.clientY
      setHeight(() => Math.max(minHeight, startHeightRef.current + (clientY - startYRef.current)))
    }
    const onUp = () => { resizingRef.current = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    window.addEventListener('touchmove', onMove, { passive: false })
    window.addEventListener('touchend', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onUp)
    }
  }, [minHeight])

  const handleInput = useCallback(() => {
    const el = editorRef.current
    if (!el) return
    isInternalChange.current = true
    onChange(el.innerHTML)
  }, [onChange])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (items) {
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (!file) return
          const reader = new FileReader()
          reader.onload = (evt) => {
            const img = new Image()
            img.onload = () => {
              const MAX_W = 800; let w = img.width, h = img.height
              if (w > MAX_W) { h = Math.round(h * MAX_W / w); w = MAX_W }
              const canvas = document.createElement('canvas')
              canvas.width = w; canvas.height = h
              canvas.getContext('2d').drawImage(img, 0, 0, w, h)
              const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
              const sel = window.getSelection()
              if (sel.rangeCount) {
                const range = sel.getRangeAt(0)
                range.deleteContents()
                const imgEl = document.createElement('img')
                imgEl.src = dataUrl; imgEl.className = 'rich-note-img'
                imgEl.style.cssText = 'max-width:100%;max-height:200px;object-fit:contain;border-radius:8px;margin:8px 0;display:inline-block;vertical-align:top;cursor:pointer'
                range.insertNode(imgEl)
                range.setStartAfter(imgEl); range.collapse(true)
                sel.removeAllRanges(); sel.addRange(range)
              }
              handleInput()
            }
            img.src = evt.target.result
          }
          reader.readAsDataURL(file)
          return
        }
      }
    }
    const html = e.clipboardData?.getData('text/html')
    if (html) {
      e.preventDefault()
      const doc = new DOMParser().parseFromString(html, 'text/html')
      doc.querySelectorAll('*').forEach(el => {
        el.style.background = ''; el.style.backgroundColor = ''
        el.style.fontFamily = ''; el.style.fontSize = ''; el.style.color = ''
        if (!el.getAttribute('style')?.trim()) el.removeAttribute('style')
      })
      const sel = window.getSelection()
      if (sel.rangeCount) {
        const range = sel.getRangeAt(0); range.deleteContents()
        const frag = range.createContextualFragment(doc.body.innerHTML)
        const lastNode = frag.lastChild; range.insertNode(frag)
        if (lastNode) { range.setStartAfter(lastNode); range.collapse(true); sel.removeAllRanges(); sel.addRange(range) }
      }
      handleInput(); return
    }
    const text = e.clipboardData?.getData('text/plain')
    if (text) {
      e.preventDefault()
      const sanitized = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')
      const sel = window.getSelection()
      if (sel.rangeCount) {
        const range = sel.getRangeAt(0); range.deleteContents()
        const frag = range.createContextualFragment(sanitized)
        const lastNode = frag.lastChild; range.insertNode(frag)
        if (lastNode) { range.setStartAfter(lastNode); range.collapse(true); sel.removeAllRanges(); sel.addRange(range) }
      }
      handleInput()
    }
  }, [handleInput])

  const handleEditorClick = useCallback((e) => {
    if (e.target.tagName === 'IMG') { setExpandedImg(e.target.src); return }
    if (e.target.tagName === 'A') {
      e.preventDefault()
      const href = e.target.getAttribute('href')
      if (href) window.open(href, '_blank', 'noopener,noreferrer')
    }
  }, [])

  const execCmd = (cmd, val = null) => {
    document.execCommand(cmd, false, val)
    editorRef.current?.focus()
    handleInput()
  }

  const applyColor = (color) => {
    const sel = window.getSelection()
    if (!sel.rangeCount) { setShowColors(false); return }
    const range = sel.getRangeAt(0)
    const selectedText = range.toString()
    if (!selectedText) { execCmd('foreColor', color); setShowColors(false); return }
    range.deleteContents()
    const span = document.createElement('span')
    span.style.color = color; span.textContent = selectedText
    range.insertNode(span)
    range.setStartAfter(span); range.collapse(true)
    sel.removeAllRanges(); sel.addRange(range)
    editorRef.current?.focus(); handleInput(); setShowColors(false)
  }

  const isEmpty = !value || value === '<br>' || value === '<div><br></div>'

  return (
    <div className="rich-note-wrapper">
      <div className="rich-note-toolbar">
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('bold')} title="Bold"><b>B</b></button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('italic')} title="Italic"><i>I</i></button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('underline')} title="Underline" style={{textDecoration:'underline'}}>U</button>
        <div className="rich-note-sep" />
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertUnorderedList')} title="Bullets">•</button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertOrderedList')} title="Numbers">1.</button>
        <div className="rich-note-sep" />
        <button type="button" className={`color-picker-toggle ${showColors ? 'active' : ''}`} onMouseDown={e => e.preventDefault()} onClick={() => setShowColors(!showColors)} title="Color">A</button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('removeFormat')} title="Clear">✘</button>
      </div>

      {showColors && (
        <div className="color-picker-row">
          {FONT_COLORS.map(({ color, label }) => (
            <button key={color} type="button" className="color-swatch" style={{ backgroundColor: color }}
              onMouseDown={e => e.preventDefault()} onClick={() => applyColor(color)} title={label} />
          ))}
        </div>
      )}

      <div ref={editorRef} className="rich-note-editor" contentEditable spellCheck
        autoCorrect="on" autoCapitalize="sentences"
        onInput={handleInput} onPaste={handlePaste} onClick={handleEditorClick}
        data-placeholder={placeholder} style={{ minHeight: height }} />

      <div className="rich-note-resizer"
        onMouseDown={e => { e.preventDefault(); resizingRef.current = true; startYRef.current = e.clientY; startHeightRef.current = height }}
        onTouchStart={e => { resizingRef.current = true; startYRef.current = e.touches[0].clientY; startHeightRef.current = height }} />

      {isEmpty && <div className="rich-note-placeholder">{placeholder}</div>}

      {expandedImg && (
        <div className="image-modal" onClick={() => setExpandedImg(null)}>
          <img src={expandedImg} alt="Expanded" />
        </div>
      )}
    </div>
  )
}
