import { useRef, useEffect, useCallback, useState } from 'react'

const FONT_COLORS = [
  { color: '#e2e8f0', label: 'Default' },
  { color: '#fbbf24', label: 'Yellow' },
  { color: '#4ade80', label: 'Green' },
  { color: '#f472b6', label: 'Pink' },
  { color: '#22d3ee', label: 'Cyan' },
  { color: '#fb923c', label: 'Orange' },
]

/**
 * RichNoteEditor - contentEditable rich text editor
 * Supports: typed text, Apple Pencil (via Scribble), pasted images (inline base64)
 * Props:
 *   value:       HTML string
 *   onChange:    (html) => void
 *   placeholder: string
 *   minHeight:   number (px, default 120)
 */
export default function RichNoteEditor({ value, onChange, placeholder = 'Write your notes...', minHeight = 120 }) {
  const editorRef = useRef(null)
  const isInternalChange = useRef(false)
  const isPasting = useRef(false)
  const [expandedImg, setExpandedImg] = useState(null)
  const [height, setHeight] = useState(minHeight)
  const resizingRef = useRef(false)
  const startYRef = useRef(0)
  const startHeightRef = useRef(minHeight)
  const [showColors, setShowColors] = useState(false)
  // Sync external value changes (e.g. loading from Supabase)
  useEffect(() => {
    if (isInternalChange.current) {
      isInternalChange.current = false
      return
    }
    const el = editorRef.current
    if (el && el.innerHTML !== (value || '')) {
      el.innerHTML = value || ''
    }
  }, [value])

  // Resize handler
  useEffect(() => {
    const onMove = (e) => {
      if (!resizingRef.current) return
      const clientY = e.touches ? e.touches[0].clientY : e.clientY
      const delta = clientY - startYRef.current
      setHeight(() => Math.max(minHeight, startHeightRef.current + delta))
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

  // Auto-capitalize after sentence-ending punctuation (. ? !) + space
  const autoCapitalize = useCallback(() => {
    // Skip auto-capitalize during paste operations
    if (isPasting.current) return
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return
    const range = sel.getRangeAt(0)
    if (!range.collapsed) return
    const node = range.startContainer
    if (node.nodeType !== Node.TEXT_NODE) return
    const off = range.startOffset
    const txt = node.textContent
    if (off < 1) return
    const ch = txt[off - 1]
    if (ch < 'a' || ch > 'z') return
    const upper = ch.toUpperCase()

    // Check: is this the very first letter in the editor?
    const full = editorRef.current?.textContent || ''
    const firstLetterIdx = full.search(/[a-zA-Z]/)
    if (firstLetterIdx >= 0 && full[firstLetterIdx] === ch) {
      const beforeFirst = full.substring(0, firstLetterIdx)
      if (!/[a-zA-Z]/.test(beforeFirst)) {
        node.textContent = txt.slice(0, off - 1) + upper + txt.slice(off)
        const r2 = document.createRange()
        r2.setStart(node, off)
        r2.collapse(true)
        sel.removeAllRanges()
        sel.addRange(r2)
        return
      }
    }

    // Check: letter right after ". " or "? " or "! "
    if (off >= 2 && txt[off - 2] === ' ') {
      const leftPart = txt.substring(0, off - 2)
      const trimmed = leftPart.trimEnd()

      if (trimmed.length > 0 && '.?!'.includes(trimmed[trimmed.length - 1])) {
        node.textContent = txt.slice(0, off - 1) + upper + txt.slice(off)
        const r2 = document.createRange()
        r2.setStart(node, off)
        r2.collapse(true)
        sel.removeAllRanges()
        sel.addRange(r2)
      }
    }
  }, [])

  const handleInput = useCallback(() => {
    const el = editorRef.current
    if (!el) return
    isInternalChange.current = true
    autoCapitalize()
    onChange(el.innerHTML)
  }, [onChange, autoCapitalize])

  // Dedicated paste-safe input handler that skips autoCapitalize
  const handlePasteInput = useCallback(() => {
    const el = editorRef.current
    if (!el) return
    isInternalChange.current = true
    onChange(el.innerHTML)
  }, [onChange])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items

    // Check for pasted images first
    if (items) {
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (!file) return

          // Compress and insert image
          const reader = new FileReader()
          reader.onload = (evt) => {
            const img = new Image()
            img.onload = () => {
              // Resize if too large (max 800px wide)
              const MAX_W = 800
              let w = img.width, h = img.height
              if (w > MAX_W) { h = Math.round(h * MAX_W / w); w = MAX_W }
              const canvas = document.createElement('canvas')
              canvas.width = w; canvas.height = h
              const ctx = canvas.getContext('2d')
              ctx.drawImage(img, 0, 0, w, h)
              const dataUrl = canvas.toDataURL('image/jpeg', 0.7)

              // Insert at cursor
              const sel = window.getSelection()
              if (sel.rangeCount) {
                const range = sel.getRangeAt(0)
                range.deleteContents()
                const imgEl = document.createElement('img')
                imgEl.src = dataUrl
                imgEl.className = 'rich-note-img'
                imgEl.style.maxWidth = '100%'
                imgEl.style.maxHeight = '200px'
                imgEl.style.objectFit = 'contain'
                imgEl.style.borderRadius = '8px'
                imgEl.style.margin = '8px 0'
                imgEl.style.display = 'inline-block'
                imgEl.style.verticalAlign = 'top'
                imgEl.style.cursor = 'pointer'
                range.insertNode(imgEl)
                // Move cursor after image
                range.setStartAfter(imgEl)
                range.collapse(true)
                sel.removeAllRanges()
                sel.addRange(range)
              }
              handlePasteInput()
            }
            img.src = evt.target.result
          }
          reader.readAsDataURL(file)
          return
        }
      }
    }

    // Smart clean paste (keep formatting, remove bad styles)
    const html = e.clipboardData?.getData('text/html')
    if (html) {
      e.preventDefault()
      isPasting.current = true
      const parser = new DOMParser()
      const doc = parser.parseFromString(html, 'text/html')
      // Remove background colors and font overrides
      doc.querySelectorAll('*').forEach(el => {
        el.style.background = ''
        el.style.backgroundColor = ''
        el.style.fontFamily = ''
        el.style.fontSize = ''
        // Remove inline color but allow default
        if (el.style.color) {
          el.style.color = ''
        }
        // Remove empty style attributes so CSS inheritance works
        if (!el.getAttribute('style')?.trim()) {
          el.removeAttribute('style')
        }
      })

      // Use DOM insertion instead of deprecated execCommand
      const sel = window.getSelection()
      if (sel.rangeCount) {
        const range = sel.getRangeAt(0)
        range.deleteContents()
        const frag = range.createContextualFragment(doc.body.innerHTML)
        const lastNode = frag.lastChild
        range.insertNode(frag)
        if (lastNode) {
          range.setStartAfter(lastNode)
          range.collapse(true)
          sel.removeAllRanges()
          sel.addRange(range)
        }
      }
      handlePasteInput()
      isPasting.current = false
      return
    }

    // Plain text fallback - prevents uncontrolled browser paste
    const text = e.clipboardData?.getData('text/plain')
    if (text) {
      e.preventDefault()
      isPasting.current = true
      const sanitized = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')

      const sel = window.getSelection()
      if (sel.rangeCount) {
        const range = sel.getRangeAt(0)
        range.deleteContents()
        const frag = range.createContextualFragment(sanitized)
        const lastNode = frag.lastChild
        range.insertNode(frag)
        if (lastNode) {
          range.setStartAfter(lastNode)
          range.collapse(true)
          sel.removeAllRanges()
          sel.addRange(range)
        }
      }
      handlePasteInput()
      isPasting.current = false
      return
    }
  }, [handlePasteInput])

  // Handle clicking on images or links in the editor
  const handleEditorClick = useCallback((e) => {
    const target = e.target
    // Image: open in modal
    if (target.tagName === 'IMG') {
      setExpandedImg(target.src)
      return
    }
    // Link: open in new tab so the app stays in the current tab
    if (target.tagName === 'A') {
      e.preventDefault()
      const href = target.getAttribute('href')
      if (href) {
        window.open(href, '_blank', 'noopener,noreferrer')
      }
    }
  }, [])

  const execCmd = (cmd, val = null) => {
    document.execCommand(cmd, false, val)
    editorRef.current?.focus()
    handleInput()
  }

  const applyColor = (color) => {
    // Save selection before any DOM changes
    const sel = window.getSelection()
    if (!sel.rangeCount) { setShowColors(false); return }
    const range = sel.getRangeAt(0)
    const selectedText = range.toString()

    if (!selectedText) {
      // No selection: just use foreColor for cursor-forward typing
      execCmd('foreColor', color)
      setShowColors(false)
      return
    }

    // Wrap selected text in a span with inline style (beats CSS specificity)
    range.deleteContents()
    const span = document.createElement('span')
    span.style.color = color
    span.textContent = selectedText
    range.insertNode(span)

    // Move cursor after the span
    range.setStartAfter(span)
    range.collapse(true)
    sel.removeAllRanges()
    sel.addRange(range)

    editorRef.current?.focus()
    handleInput()
    setShowColors(false)
  }

  const isEmpty = !value || value === '<br>' || value === '<div><br></div>'

  return (
    <div className="rich-note-editor">
              <div className="rich-note-toolbar">
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('bold')} title="Bold" aria-label="Bold">B</button>
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('italic')} title="Italic" aria-label="Italic"><em>I</em></button>
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('underline')} title="Underline" aria-label="Underline">U</button>
        <span className="rne-toolbar-sep" />
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertUnorderedList')} title="Bullet list" aria-label="Bullet list">{"\u2022"}</button>
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertOrderedList')} title="Numbered list" aria-label="Numbered list">1.</button>
        <span className="rne-toolbar-sep" />
        <span className="color-picker-toggle">
            <button onMouseDown={e => e.preventDefault()} onClick={() => setShowColors(!showColors)} title="Font color" aria-label="Choose text color"
            >A</button>
            {showColors && (
              <div className="color-picker-row">
                {FONT_COLORS.map(({ color, label }) => (
                  <button key={color} className="color-swatch" style={{ backgroundColor: color }} onMouseDown={e => e.preventDefault()} onClick={() => applyColor(color)} title={label} />
                ))}
              </div>
            )}
            </span>
            <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('removeFormat')} title="Clear formatting" aria-label="Clear formatting">{"\u2718"}</button>
          </div>
      <div
        ref={editorRef}
        className="rne-content"
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onPaste={handlePaste}
        onClick={handleEditorClick}
        style={{ minHeight: height }}
        role="textbox"
        aria-multiline="true"
        aria-label={placeholder}
      />
      <div
        className="rich-note-resizer"
        onMouseDown={(e) => {
          e.preventDefault()
          resizingRef.current = true
          startYRef.current = e.clientY
          startHeightRef.current = height
        }}
        onTouchStart={(e) => {
          resizingRef.current = true
          startYRef.current = e.touches[0].clientY
          startHeightRef.current = height
        }}
      />
      {isEmpty && (
        <div className="rich-note-placeholder">
          {placeholder}
        </div>
      )}
      {expandedImg && (
        <div className="image-modal" onClick={() => setExpandedImg(null)}>
          <img src={expandedImg} alt="Expanded view" />
        </div>
      )}
    </div>
  )
}
