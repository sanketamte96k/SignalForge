import { useEffect, useRef } from 'react'
import './KeyboardShortcutsModal.css'
import { SHORTCUT_GROUPS } from './keyboardShortcuts'

export default function KeyboardShortcutsModal({ isOpen, onClose }) {
  const modalRef = useRef(null)
  const closeBtnRef = useRef(null)
  const triggerRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return

    triggerRef.current = document.activeElement

    // Focus close button on open
    const timer = setTimeout(() => {
      if (closeBtnRef.current) {
        closeBtnRef.current.focus()
      }
    }, 50)

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
        return
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length > 0) {
          const first = focusable[0]
          const last = focusable[focusable.length - 1]
          if (e.shiftKey) {
            if (document.activeElement === first || !modalRef.current.contains(document.activeElement)) {
              e.preventDefault()
              last.focus()
            }
          } else {
            if (document.activeElement === last || !modalRef.current.contains(document.activeElement)) {
              e.preventDefault()
              first.focus()
            }
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('keydown', handleKeyDown)
      if (triggerRef.current && typeof triggerRef.current.focus === 'function') {
        triggerRef.current.focus()
      }
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="shortcuts-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="shortcuts-modal-container"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
      >
        <div className="shortcuts-modal-header">
          <div className="shortcuts-header-left">
            <span className="shortcuts-badge">POWER-USER UX</span>
            <h2 id="shortcuts-modal-title">Keyboard Shortcuts</h2>
          </div>

          <button
            type="button"
            className="shortcuts-close-btn"
            ref={closeBtnRef}
            onClick={onClose}
            aria-label="Close shortcuts dialog (Esc)"
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>

        <div className="shortcuts-modal-body">
          <div className="shortcuts-grid">
            {SHORTCUT_GROUPS.map((group) => (
              <div className="shortcuts-group-card" key={group.category}>
                <h3 className="shortcuts-group-title">{group.category}</h3>
                <ul className="shortcuts-list">
                  {group.shortcuts.map((sc) => (
                    <li className="shortcut-item" key={sc.key}>
                      <span className="shortcut-desc">{sc.description}</span>
                      <kbd className="shortcut-key">{sc.key}</kbd>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="shortcuts-modal-footer">
          <span>
            Press <kbd className="shortcut-key-mini">Esc</kbd> anytime to close this help dialog.
          </span>
          <button
            type="button"
            className="shortcuts-done-btn"
            onClick={onClose}
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
