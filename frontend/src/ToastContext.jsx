/**
 * ToastContext.jsx
 * Centralized toast / notification system for SignalForge.
 *
 * Architecture:
 *   - ToastProvider  — wraps the app, owns toast state
 *   - ToastContainer — fixed portal that renders the stack
 *   - ToastItem      — individual animated toast card
 *
 * The useToast hook lives in useToast.js to satisfy the
 * react/only-export-components linting rule.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import './ToastContext.css'
import { ToastContext } from './useToast'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_DURATION = {
  success: 4000,
  info: 4500,
  warning: 5000,
  error: 6000,
}

const MAX_TOASTS = 5
const DEDUPE_WINDOW_MS = 1500


// ---------------------------------------------------------------------------
// ToastItem
// ---------------------------------------------------------------------------

function ToastItem({ toast, onDismiss }) {
  const [exiting, setExiting] = useState(false)
  const progressRef = useRef(null)
  const startTimeRef = useRef(null)
  const rafRef = useRef(null)
  const timeoutRef = useRef(null)

  const dismiss = useCallback(() => {
    if (exiting) return
    setExiting(true)
    // Give the exit animation time to play before removing
    setTimeout(() => onDismiss(toast.id), 280)
  }, [exiting, onDismiss, toast.id])

  // Progress bar animation + auto-dismiss
  useEffect(() => {
    const duration = toast.duration
    startTimeRef.current = Date.now()

    function tick() {
      const elapsed = Date.now() - startTimeRef.current
      const pct = Math.min((elapsed / duration) * 100, 100)
      if (progressRef.current) {
        progressRef.current.style.width = `${100 - pct}%`
      }
      if (elapsed < duration) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    timeoutRef.current = window.setTimeout(dismiss, duration)

    return () => {
      cancelAnimationFrame(rafRef.current)
      clearTimeout(timeoutRef.current)
    }
  }, [dismiss, toast.duration])

  const icons = {
    success: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="9" strokeWidth="1.5" stroke="currentColor" />
        <path d="M6.5 10.5l2.5 2.5 4-5" strokeWidth="1.8" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    error: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="9" strokeWidth="1.5" stroke="currentColor" />
        <path d="M7 7l6 6M13 7l-6 6" strokeWidth="1.8" stroke="currentColor" strokeLinecap="round" />
      </svg>
    ),
    warning: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2.5L18.5 17.5H1.5L10 2.5z" strokeWidth="1.5" stroke="currentColor" strokeLinejoin="round" />
        <path d="M10 8v4" strokeWidth="1.8" stroke="currentColor" strokeLinecap="round" />
        <circle cx="10" cy="14.5" r="0.75" fill="currentColor" />
      </svg>
    ),
    info: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="9" strokeWidth="1.5" stroke="currentColor" />
        <path d="M10 9v5" strokeWidth="1.8" stroke="currentColor" strokeLinecap="round" />
        <circle cx="10" cy="6.5" r="0.75" fill="currentColor" />
      </svg>
    ),
  }

  return (
    <div
      className={`sf-toast sf-toast--${toast.type} ${exiting ? 'sf-toast--exit' : 'sf-toast--enter'}`}
      role={toast.type === 'error' || toast.type === 'warning' ? 'alert' : 'status'}
      aria-live={toast.type === 'error' || toast.type === 'warning' ? 'assertive' : 'polite'}
      aria-atomic="true"
    >
      <div className="sf-toast__icon" aria-hidden="true">
        {icons[toast.type]}
      </div>

      <div className="sf-toast__body">
        {toast.title && (
          <strong className="sf-toast__title">{toast.title}</strong>
        )}
        <span className="sf-toast__message">{toast.message}</span>
      </div>

      <button
        type="button"
        className="sf-toast__close"
        onClick={dismiss}
        aria-label="Dismiss notification"
      >
        ✕
      </button>

      <div className="sf-toast__progress-track" aria-hidden="true">
        <div ref={progressRef} className="sf-toast__progress-bar" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ToastContainer
// ---------------------------------------------------------------------------

function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null

  return (
    <div className="sf-toast-container" aria-label="Notifications">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ToastProvider
// ---------------------------------------------------------------------------

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  // Tracks recent (type+message) combos for deduplication
  const recentRef = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    ({ type = 'info', title = '', message = '', duration }) => {
      if (!message) return

      const dedupKey = `${type}:${message}`
      const now = Date.now()
      const lastSeen = recentRef.current.get(dedupKey)

      if (lastSeen && now - lastSeen < DEDUPE_WINDOW_MS) {
        // Duplicate within dedup window — ignore
        return
      }

      recentRef.current.set(dedupKey, now)

      // Clean up old dedupe keys (keep map lean)
      if (recentRef.current.size > 50) {
        const cutoff = now - DEDUPE_WINDOW_MS * 10
        for (const [key, ts] of recentRef.current.entries()) {
          if (ts < cutoff) recentRef.current.delete(key)
        }
      }

      const resolvedDuration =
        typeof duration === 'number' && duration > 0
          ? duration
          : DEFAULT_DURATION[type] ?? 4500

      const id = `toast-${now}-${Math.random().toString(36).slice(2, 7)}`

      setToasts((prev) => {
        const next = [...prev, { id, type, title, message, duration: resolvedDuration }]
        // Trim to max — remove oldest first
        return next.length > MAX_TOASTS ? next.slice(next.length - MAX_TOASTS) : next
      })
    },
    [],
  )

  // Stable api object — only changes when addToast/dismiss change (never).
  // Without useMemo, every toast add/dismiss causes all useToast() consumers
  // to re-render because a new api object reference is created each render.
  const api = useMemo(() => ({
    success: (message, opts) => addToast({ type: 'success', message, ...opts }),
    error: (message, opts) => addToast({ type: 'error', message, ...opts }),
    warning: (message, opts) => addToast({ type: 'warning', message, ...opts }),
    info: (message, opts) => addToast({ type: 'info', message, ...opts }),
    dismiss,
  }), [addToast, dismiss])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

// Default export
export default ToastProvider
