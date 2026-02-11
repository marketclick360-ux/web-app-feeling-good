import { useRef, useEffect, useCallback, useState } from 'react'

/**
 * RichNoteEditor — contentEditable rich text editor
 * Supports: typed text, Apple Pencil (via Scribble), pasted images (inline base64)
 * Props:
 *   value: HTML string
 *   onChange: (html) => void
 *   placeholder: string
 *   minHeight: number (px, default 120)
 */
export default function RichNoteEditor({ value, onChange, placeholder = 'Write your notes...', minHeight = 120 }) {
  const editorRef = useRef(null)
  const isInternalChange = useRef(false)
  const [expandedImg, setExpandedImg] = useState(null)

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

  const handleInput = useCallback(() => {
    const el = editorRef.current
    if (!el) return
    isInternalChange.current = true
    onChange(el.innerHTML)
  }, [onChange])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return

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
              imgEl.style.display = 'block'
              imgEl.style.cursor = 'pointer'
              range.insertNode(imgEl)
              // Move cursor after image
              range.setStartAfter(imgEl)
              range.collapse(true)
              sel.removeAllRanges()
              sel.addRange(range)
            }
            handleInput()
          }
          img.src = evt.target.result
        }
        reader.readAsDataURL(file)
        return
      }
    }
  }, [handleInput])

  // Handle clicking on images in the editor to expand them
  const handleEditorClick = useCallback((e) => {
    if (e.target.tagName === 'IMG') {
      setExpandedImg(e.target.src)
    }
  }, [])

  const execCmd = (cmd, val = null) => {
    document.execCommand(cmd, false, val)
    editorRef.current?.focus()
    handleInput()
  }

  const isEmpty = !value || value === '<br>' || value === '<div><br></div>'

  return (
    <div className="rich-note-wrapper">
      <div className="rich-note-toolbar">
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('bold')} title="Bold">B</button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('italic')} title="Italic"><em>I</em></button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('underline')} title="Underline"><u>U</u></button>
        <span className="rich-note-sep" />
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertUnorderedList')} title="Bullet list">{"\u2022"}</button>
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('insertOrderedList')} title="Numbered list">1.</button>
        <span className="rich-note-sep" />
        <button type="button" onMouseDown={e => e.preventDefault()} onClick={() => execCmd('removeFormat')} title="Clear formatting">{"\u2718"}</button>
      </div>
      <div
        ref={editorRef}
        className="rich-note-editor"
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onPaste={handlePaste}
        onClick={handleEditorClick}
        style={{ minHeight: minHeight + 'px' }}
        data-placeholder={placeholder}
      />
      {isEmpty && <div className="rich-note-placeholder">{placeholder}</div>}

      <div
        className="image-modal"
        style={{ display: expandedImg ? 'flex' : 'none' }}
        onClick={() => setExpandedImg(null)}
      >
        <img src={expandedImg || ''} alt="Expanded view" />
      </div>
    </div>
  )
}
