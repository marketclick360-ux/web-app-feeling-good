import { useRef, useEffect, useCallback, useState } from 'react'

const FONT_COLORS = [
  { color: '#e2e8f0', label: 'Default' },
  { color: '#fbbf24', label: 'Yellow' },
  { color: '#4ade80', label: 'Green' },
  { color: '#f472b6', label: 'Pink' },
  { color: '#22d3ee', label: 'Cyan' },
  { color: '#fb923c', label: 'Orange' },
]

const PEN_COLORS = ['#e2e8f0','#fbbf24','#4ade80','#f472b6','#22d3ee','#fb923c','#ef4444']

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
  const colorPickerRef = useRef(null)
  const [showDrawing, setShowDrawing] = useState(false)
  const canvasRef = useRef(null)
  const drawCtxRef = useRef(null)
  const isDrawingRef = useRef(false)
  const lastPt = useRef(null)
  const [penColor, setPenColor] = useState('#e2e8f0')
  const [penSize, setPenSize] = useState(2)
  const [eraserOn, setEraserOn] = useState(false)

  // Sync external value
  useEffect(() => {
    if (isInternalChange.current) { isInternalChange.current = false; return }
    const el = editorRef.current
    if (el && el.innerHTML !== (value || '')) el.innerHTML = value || ''
  }, [value])

  // Close color picker on click outside
  useEffect(() => {
    if (!showColors) return
    const handler = (e) => { if (colorPickerRef.current && !colorPickerRef.current.contains(e.target)) setShowColors(false) }
    document.addEventListener('mousedown', handler)
    document.addEventListener('touchstart', handler)
    return () => { document.removeEventListener('mousedown', handler); document.removeEventListener('touchstart', handler) }
  }, [showColors])

  // Resize handler
  useEffect(() => {
    const onMove = (e) => { if (!resizingRef.current) return; const clientY = e.touches ? e.touches[0].clientY : e.clientY; setHeight(() => Math.max(minHeight, startHeightRef.current + clientY - startYRef.current)) }
    const onUp = () => { resizingRef.current = false }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
    window.addEventListener('touchmove', onMove, { passive: false }); window.addEventListener('touchend', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); window.removeEventListener('touchmove', onMove); window.removeEventListener('touchend', onUp) }
  }, [minHeight])

  // Init canvas when drawing opens
  useEffect(() => {
    if (!showDrawing) return
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.parentElement.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = 400 * dpr
    canvas.style.width = rect.width + 'px'
    canvas.style.height = '400px'
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.fillStyle = '#1e1b3a'
    ctx.fillRect(0, 0, rect.width, 400)
    drawCtxRef.current = ctx
  }, [showDrawing])

  const getPos = (e) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const t = e.touches ? e.touches[0] : e
    return { x: t.clientX - rect.left, y: t.clientY - rect.top, pressure: e.pressure || t.force || 0.5 }
  }

  const startDraw = (e) => {
    e.preventDefault()
    isDrawingRef.current = true
    lastPt.current = getPos(e)
  }
  const moveDraw = (e) => {
    e.preventDefault()
    if (!isDrawingRef.current) return
    const ctx = drawCtxRef.current
    if (!ctx) return
    const pt = getPos(e)
    if (!pt || !lastPt.current) return
    ctx.beginPath()
    if (eraserOn) {
      ctx.globalCompositeOperation = 'destination-out'
      ctx.lineWidth = penSize * 8
    } else {
      ctx.globalCompositeOperation = 'source-over'
      ctx.strokeStyle = penColor
      ctx.lineWidth = Math.max(1, penSize * (0.5 + pt.pressure))
    }
    ctx.moveTo(lastPt.current.x, lastPt.current.y)
    ctx.lineTo(pt.x, pt.y)
    ctx.stroke()
    lastPt.current = pt
  }
  const endDraw = () => { isDrawingRef.current = false; lastPt.current = null }

  const clearCanvas = () => {
    const canvas = canvasRef.current
    const ctx = drawCtxRef.current
    if (!canvas || !ctx) return
    const dpr = window.devicePixelRatio || 1
    ctx.globalCompositeOperation = 'source-over'
    ctx.fillStyle = '#1e1b3a'
    ctx.fillRect(0, 0, canvas.width / dpr, canvas.height / dpr)
  }

  const insertDrawing = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dataUrl = canvas.toDataURL('image/png')
    const el = editorRef.current
    if (!el) return
    const img = document.createElement('img')
    img.src = dataUrl
    img.className = 'rich-note-img'
    img.style.maxWidth = '100%'
    img.style.borderRadius = '8px'
    img.style.margin = '8px 0'
    img.style.display = 'block'
    img.style.cursor = 'pointer'
    el.appendChild(img)
    el.appendChild(document.createElement('br'))
    isInternalChange.current = true
    onChange(el.innerHTML)
    setShowDrawing(false)
  }

  // Auto-capitalize after sentence-ending punctuation
  const autoCapitalize = useCallback(() => {
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
    const full = editorRef.current?.textContent || ''
    const firstLetterIdx = full.search(/[a-zA-Z]/)
    if (firstLetterIdx >= 0 && full[firstLetterIdx] === ch) {
      const beforeFirst = full.substring(0, firstLetterIdx)
      if (!/[a-zA-Z]/.test(beforeFirst)) {
        node.textContent = txt.slice(0, off - 1) + upper + txt.slice(off)
        const r2 = document.createRange(); r2.setStart(node, off); r2.collapse(true); sel.removeAllRanges(); sel.addRange(r2); return
      }
    }
    if (off >= 2 && txt[off - 2] === ' ') {
      const leftPart = txt.substring(0, off - 2)
      const trimmed = leftPart.trimEnd()
      if (trimmed.length > 0 && '.?!'.includes(trimmed[trimmed.length - 1])) {
        node.textContent = txt.slice(0, off - 1) + upper + txt.slice(off)
        const r2 = document.createRange(); r2.setStart(node, off); r2.collapse(true); sel.removeAllRanges(); sel.addRange(r2)
      }
    }
  }, [])

  const handleInput = useCallback(() => {
    const el = editorRef.current; if (!el) return
    isInternalChange.current = true; autoCapitalize(); onChange(el.innerHTML)
  }, [onChange, autoCapitalize])

  const handlePasteInput = useCallback(() => {
    const el = editorRef.current; if (!el) return
    isInternalChange.current = true; onChange(el.innerHTML)
  }, [onChange])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (items) {
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile(); if (!file) return
          const reader = new FileReader()
          reader.onload = (evt) => {
            const img = new Image()
            img.onload = () => {
              const MAX_W = 800; let w = img.width, h = img.height
              if (w > MAX_W) { h = Math.round(h * MAX_W / w); w = MAX_W }
              const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h
              const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0, w, h)
              const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
              const sel = window.getSelection()
              if (sel.rangeCount) {
                const range = sel.getRangeAt(0); range.deleteContents()
                const imgEl = document.createElement('img'); imgEl.src = dataUrl; imgEl.className = 'rich-note-img'
                imgEl.style.maxWidth = '100%'; imgEl.style.maxHeight = '200px'; imgEl.style.objectFit = 'contain'
                imgEl.style.borderRadius = '8px'; imgEl.style.margin = '8px 0'; imgEl.style.display = 'inline-block'
                imgEl.style.verticalAlign = 'top'; imgEl.style.cursor = 'pointer'
                range.insertNode(imgEl); range.setStartAfter(imgEl); range.collapse(true); sel.removeAllRanges(); sel.addRange(range)
              }
              handlePasteInput()
            }; img.src = evt.target.result
          }; reader.readAsDataURL(file); return
        }
      }
    }
    const html = e.clipboardData?.getData('text/html')
    if (html) {
      e.preventDefault(); isPasting.current = true
      const parser = new DOMParser(); const doc = parser.parseFromString(html, 'text/html')
      doc.querySelectorAll('*').forEach(el => { el.style.background = ''; el.style.backgroundColor = ''; el.style.fontFamily = ''; el.style.fontSize = ''; if (el.style.color) el.style.color = ''; if (!el.getAttribute('style')?.trim()) el.removeAttribute('style') })
      const sel = window.getSelection()
      if (sel.rangeCount) { const range = sel.getRangeAt(0); range.deleteContents(); const frag = range.createContextualFragment(doc.body.innerHTML); const lastNode = frag.lastChild; range.insertNode(frag); if (lastNode) { range.setStartAfter(lastNode); range.collapse(true); sel.removeAllRanges(); sel.addRange(range) } }
      handlePasteInput(); isPasting.current = false; return
    }
    const text = e.clipboardData?.getData('text/plain')
    if (text) {
      e.preventDefault(); isPasting.current = true
      const sanitized = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
      const sel = window.getSelection()
      if (sel.rangeCount) { const range = sel.getRangeAt(0); range.deleteContents(); const frag = range.createContextualFragment(sanitized); const lastNode = frag.lastChild; range.insertNode(frag); if (lastNode) { range.setStartAfter(lastNode); range.collapse(true); sel.removeAllRanges(); sel.addRange(range) } }
      handlePasteInput(); isPasting.current = false; return
    }
  }, [handlePasteInput])

  const handleEditorClick = useCallback((e) => {
    const target = e.target
    if (target.tagName === 'IMG') { setExpandedImg(target.src); return }
    if (target.tagName === 'A') { e.preventDefault(); const href = target.getAttribute('href'); if (href) window.open(href, '_blank', 'noopener,noreferrer') }
  }, [])

  const execCmd = (cmd, val = null) => { document.execCommand(cmd, false, val); editorRef.current?.focus(); handleInput() }

  const applyColor = (color) => {
    const sel = window.getSelection()
    if (!sel.rangeCount) { setShowColors(false); return }
    const range = sel.getRangeAt(0)
    const selectedText = range.toString()
    if (!selectedText) { execCmd('foreColor', color); setShowColors(false); return }
    range.deleteContents()
    const span = document.createElement('span'); span.style.color = color; span.textContent = selectedText
    range.insertNode(span); range.setStartAfter(span); range.collapse(true); sel.removeAllRanges(); sel.addRange(range)
    editorRef.current?.focus(); handleInput(); setShowColors(false)
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
        <span ref={colorPickerRef} className="color-picker-toggle">
          <button onMouseDown={e => e.preventDefault()} onClick={() => setShowColors(!showColors)} title="Font color" aria-label="Choose text color">A</button>
          {showColors && (
            <div className="color-picker-row">
              {FONT_COLORS.map(({ color, label }) => (
                <button key={color} className="color-swatch" style={{ background: color }} onMouseDown={e => e.preventDefault()} onClick={() => applyColor(color)} title={label} />
              ))}
            </div>
          )}
        </span>
        <button onMouseDown={e => e.preventDefault()} onClick={() => execCmd('removeFormat')} title="Clear formatting" aria-label="Clear formatting">{"\u2718"}</button>
        <span className="rne-toolbar-sep" />
        <button onMouseDown={e => e.preventDefault()} onClick={() => setShowDrawing(!showDrawing)} title="Draw with Apple Pencil" aria-label="Draw" className={showDrawing ? 'rne-btn-active' : ''}>{"\u270F\uFE0F"}</button>
      </div>

      {showDrawing && (
        <div className="rne-draw-panel">
          <div className="rne-draw-tools">
            {PEN_COLORS.map(c => (
              <button key={c} className={`color-swatch ${penColor === c && !eraserOn ? 'active-swatch' : ''}`} style={{ background: c }} onClick={() => { setPenColor(c); setEraserOn(false) }} />
            ))}
            <span className="rne-toolbar-sep" />
            <button className={`rne-draw-btn ${penSize === 1 ? 'rne-btn-active' : ''}`} onClick={() => setPenSize(1)} title="Fine">{'\u00B7'}</button>
            <button className={`rne-draw-btn ${penSize === 2 ? 'rne-btn-active' : ''}`} onClick={() => setPenSize(2)} title="Medium">{'\u2022'}</button>
            <button className={`rne-draw-btn ${penSize === 4 ? 'rne-btn-active' : ''}`} onClick={() => setPenSize(4)} title="Thick">{'\u2B24'}</button>
            <span className="rne-toolbar-sep" />
            <button className={`rne-draw-btn ${eraserOn ? 'rne-btn-active' : ''}`} onClick={() => setEraserOn(!eraserOn)} title="Eraser">{'\uD83E\uDDF9'}</button>
            <button className="rne-draw-btn" onClick={clearCanvas} title="Clear all">{'\uD83D\uDDD1'}</button>
          </div>
          <canvas
            ref={canvasRef}
            className="rne-draw-canvas"
            onPointerDown={startDraw}
            onPointerMove={moveDraw}
            onPointerUp={endDraw}
            onPointerLeave={endDraw}
            onTouchStart={startDraw}
            onTouchMove={moveDraw}
            onTouchEnd={endDraw}
            style={{ touchAction: 'none' }}
          />
          <div className="rne-draw-actions">
            <button className="rne-draw-btn rne-draw-cancel" onClick={() => setShowDrawing(false)}>Cancel</button>
            <button className="rne-draw-btn rne-draw-insert" onClick={insertDrawing}>Insert Drawing</button>
          </div>
        </div>
      )}

      <div
        ref={editorRef}
        className="rne-content"
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onPaste={handlePaste}
        onClick={handleEditorClick}
        style={{ height, overflowY: 'auto' }}
        role="textbox"
        aria-multiline="true"
        aria-label={placeholder}
      />
      <div
        className="rich-note-resizer"
        onMouseDown={(e) => { e.preventDefault(); resizingRef.current = true; startYRef.current = e.clientY; startHeightRef.current = height }}
        onTouchStart={(e) => { resizingRef.current = true; startYRef.current = e.touches[0].clientY; startHeightRef.current = height }}
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
