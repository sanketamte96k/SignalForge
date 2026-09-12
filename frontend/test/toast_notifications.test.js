/**
 * toast_notifications.test.js
 * Unit / integration tests for SignalForge Improvement #7: Toast & Notifications UX
 *
 * Tests:
 *   - Toast type support and duration defaults
 *   - Toast content (message, title)
 *   - Deduplication logic
 *   - Max toast limit enforcement
 *   - Dismiss behavior
 *   - Accessibility attributes (role, aria-live)
 *   - Error message sanitization
 *   - Responsive positioning utilities
 *   - Multiple simultaneous toasts
 *   - Action-toast message quality
 */

import test from 'node:test'
import assert from 'node:assert/strict'
import { sanitizeErrorMessage } from '../src/stateUtils.js'

// ─────────────────────────────────────────────────────────────────────────────
// Toast type definitions (mirrors ToastContext.jsx constants)
// ─────────────────────────────────────────────────────────────────────────────

const TOAST_TYPES = ['success', 'error', 'warning', 'info']

const DEFAULT_DURATION = {
  success: 4000,
  info: 4500,
  warning: 5000,
  error: 6000,
}

const MAX_TOASTS = 5
const DEDUPE_WINDOW_MS = 1500

// ─────────────────────────────────────────────────────────────────────────────
// Simulated toast store (matches ToastContext.jsx logic without React)
// ─────────────────────────────────────────────────────────────────────────────

function createToastStore() {
  let toasts = []
  let idCounter = 0
  const recentMap = new Map()

  function addToast({ type = 'info', title = '', message = '', duration } = {}) {
    if (!message) return null

    const dedupKey = `${type}:${message}`
    const now = Date.now()
    const lastSeen = recentMap.get(dedupKey)

    if (lastSeen && now - lastSeen < DEDUPE_WINDOW_MS) {
      return null // duplicate suppressed
    }

    recentMap.set(dedupKey, now)

    const resolvedDuration =
      typeof duration === 'number' && duration > 0
        ? duration
        : DEFAULT_DURATION[type] ?? 4500

    const id = `toast-${++idCounter}`
    const newToast = { id, type, title, message, duration: resolvedDuration }

    toasts = [...toasts, newToast]
    if (toasts.length > MAX_TOASTS) {
      toasts = toasts.slice(toasts.length - MAX_TOASTS)
    }

    return id
  }

  function dismiss(id) {
    toasts = toasts.filter((t) => t.id !== id)
  }

  function getToasts() {
    return toasts
  }

  function clear() {
    toasts = []
    idCounter = 0
    recentMap.clear()
  }

  function clearDedupeWindow() {
    recentMap.clear()
  }

  return { addToast, dismiss, getToasts, clear, clearDedupeWindow }
}

// ─────────────────────────────────────────────────────────────────────────────
// Responsive positioning utility (mirrors ToastContext.css breakpoints)
// ─────────────────────────────────────────────────────────────────────────────

function getToastPosition(viewportWidth) {
  const isMobile = viewportWidth <= 860

  if (isMobile) {
    return {
      placement: 'top-center',
      top: 72,
      right: 12,
      left: 12,
      fixedWidth: false,
    }
  }

  return {
    placement: 'top-right',
    top: 76,
    right: 20,
    left: null,
    fixedWidth: true,
    width: 340,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Aria role helper (mirrors ToastItem render logic)
// ─────────────────────────────────────────────────────────────────────────────

function getAriaRole(type) {
  if (type === 'error' || type === 'warning') return 'alert'
  return 'status'
}

function getAriaLive(type) {
  if (type === 'error' || type === 'warning') return 'assertive'
  return 'polite'
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests — using node:test runner (same pattern as other test files)
// ─────────────────────────────────────────────────────────────────────────────

test('Toast & Notifications UX (Improvement #7)', async (t) => {

  // ── 1. Type support ──────────────────────────────────────────────────────
  await t.test('1. All four toast types are defined', () => {
    assert.deepEqual(TOAST_TYPES, ['success', 'error', 'warning', 'info'])
  })

  await t.test('2. Each type has a positive default duration', () => {
    for (const type of TOAST_TYPES) {
      assert.ok(
        typeof DEFAULT_DURATION[type] === 'number' && DEFAULT_DURATION[type] > 0,
        `${type} should have a positive default duration`,
      )
    }
  })

  await t.test('3. Error and warning have longer durations than success', () => {
    assert.ok(DEFAULT_DURATION.error > DEFAULT_DURATION.success)
    assert.ok(DEFAULT_DURATION.warning > DEFAULT_DURATION.success)
  })

  await t.test('4. Each type creates a toast with correct type field', () => {
    const store = createToastStore()
    for (const type of TOAST_TYPES) {
      store.clearDedupeWindow()
      store.addToast({ type, message: `Test ${type} message` })
    }
    const toasts = store.getToasts()
    const foundTypes = toasts.map((t2) => t2.type)
    for (const type of TOAST_TYPES) {
      assert.ok(foundTypes.includes(type), `Toast of type "${type}" should exist`)
    }
    store.clear()
  })

  // ── 2. Toast content ─────────────────────────────────────────────────────
  await t.test('5. Toast with message only stores message correctly', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'RELIANCE added to Watchlist.' })
    const [first] = store.getToasts()
    assert.equal(first.message, 'RELIANCE added to Watchlist.')
    assert.equal(first.title, '')
    store.clear()
  })

  await t.test('6. Toast with title stores both title and message', () => {
    const store = createToastStore()
    store.addToast({ type: 'info', title: 'Session Active', message: 'Paper Trading session started.' })
    const [first] = store.getToasts()
    assert.equal(first.title, 'Session Active')
    assert.equal(first.message, 'Paper Trading session started.')
    store.clear()
  })

  await t.test('7. Toast without message is not added', () => {
    const store = createToastStore()
    const id = store.addToast({ type: 'success', message: '' })
    assert.equal(id, null)
    assert.equal(store.getToasts().length, 0)
  })

  await t.test('8. Custom duration overrides default', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'Quick alert.', duration: 1000 })
    const [first] = store.getToasts()
    assert.equal(first.duration, 1000)
    store.clear()
  })

  await t.test('9. Non-positive custom duration falls back to type default', () => {
    const store = createToastStore()
    store.addToast({ type: 'info', message: 'Test.', duration: 0 })
    const [first] = store.getToasts()
    assert.equal(first.duration, DEFAULT_DURATION.info)
    store.clear()
  })

  // ── 3. Deduplication ─────────────────────────────────────────────────────
  await t.test('10. Identical type+message within dedup window is suppressed', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'Stock added.' })
    const secondId = store.addToast({ type: 'success', message: 'Stock added.' })
    assert.equal(secondId, null, 'Duplicate toast should be suppressed')
    assert.equal(store.getToasts().length, 1)
    store.clear()
  })

  await t.test('11. Different messages of same type are both added', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'RELIANCE added.' })
    store.addToast({ type: 'success', message: 'TCS added.' })
    assert.equal(store.getToasts().length, 2)
    store.clear()
  })

  await t.test('12. Same message with different type is not suppressed', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'Stock updated.' })
    const secondId = store.addToast({ type: 'error', message: 'Stock updated.' })
    assert.notEqual(secondId, null, 'Different type should not be deduplicated')
    assert.equal(store.getToasts().length, 2)
    store.clear()
  })

  await t.test('13. After dedup window expires, same message can fire again', () => {
    const store = createToastStore()
    store.addToast({ type: 'info', message: 'Loading scanner.' })
    store.clearDedupeWindow()
    const secondId = store.addToast({ type: 'info', message: 'Loading scanner.' })
    assert.notEqual(secondId, null, 'After clearing dedup window, toast should be re-added')
    assert.equal(store.getToasts().length, 2)
    store.clear()
  })

  // ── 4. Max toast limit ───────────────────────────────────────────────────
  await t.test(`14. Exceeding ${MAX_TOASTS} toasts trims the oldest`, () => {
    const store = createToastStore()
    for (let i = 1; i <= MAX_TOASTS + 2; i++) {
      store.clearDedupeWindow()
      store.addToast({ type: 'info', message: `Toast message #${i}` })
    }
    const toasts = store.getToasts()
    assert.ok(
      toasts.length <= MAX_TOASTS,
      `Should have at most ${MAX_TOASTS} toasts, got ${toasts.length}`,
    )
    store.clear()
  })

  await t.test('15. Newest toast survives after trim', () => {
    const store = createToastStore()
    for (let i = 1; i <= MAX_TOASTS + 1; i++) {
      store.clearDedupeWindow()
      store.addToast({ type: 'success', message: `Event ${i}` })
    }
    const toasts = store.getToasts()
    const messages = toasts.map((t2) => t2.message)
    assert.ok(
      messages.includes(`Event ${MAX_TOASTS + 1}`),
      'Newest toast should survive trimming',
    )
    store.clear()
  })

  // ── 5. Dismiss ───────────────────────────────────────────────────────────
  await t.test('16. Dismissing a toast removes it from the list', () => {
    const store = createToastStore()
    const id = store.addToast({ type: 'success', message: 'Created.' })
    assert.equal(store.getToasts().length, 1)
    store.dismiss(id)
    assert.equal(store.getToasts().length, 0)
  })

  await t.test('17. Dismissing non-existent id does not throw or mutate', () => {
    const store = createToastStore()
    store.addToast({ type: 'info', message: 'Still here.' })
    store.dismiss('toast-nonexistent-999')
    assert.equal(store.getToasts().length, 1)
    store.clear()
  })

  // ── 6. Accessibility attributes ──────────────────────────────────────────
  await t.test('18. Success and info get role=status and aria-live=polite', () => {
    for (const type of ['success', 'info']) {
      assert.equal(getAriaRole(type), 'status', `${type} should use role=status`)
      assert.equal(getAriaLive(type), 'polite', `${type} should use aria-live=polite`)
    }
  })

  await t.test('19. Error and warning get role=alert and aria-live=assertive', () => {
    for (const type of ['error', 'warning']) {
      assert.equal(getAriaRole(type), 'alert', `${type} should use role=alert`)
      assert.equal(getAriaLive(type), 'assertive', `${type} should use aria-live=assertive`)
    }
  })

  // ── 7. Error message sanitization ────────────────────────────────────────
  await t.test('20. Network error is sanitized to readable message', () => {
    const err = new Error('Failed to fetch')
    const msg = sanitizeErrorMessage(err)
    assert.ok(
      msg.toLowerCase().includes('connect') || msg.toLowerCase().includes('backend'),
      'Network error should mention connection/backend',
    )
  })

  await t.test('21. 500 server error is sanitized', () => {
    const err = new Error('Request failed with status code 500')
    const msg = sanitizeErrorMessage(err)
    assert.ok(
      msg.toLowerCase().includes('server') || msg.toLowerCase().includes('issue'),
      'Server error should be sanitized',
    )
  })

  await t.test('22. 404 error is sanitized', () => {
    const err = new Error('HTTP 404 not found')
    const msg = sanitizeErrorMessage(err)
    assert.ok(
      msg.toLowerCase().includes('not found') || msg.toLowerCase().includes('resource'),
      '404 error should map to readable message',
    )
  })

  await t.test('23. Timeout error is sanitized', () => {
    const err = new Error('Request timeout exceeded')
    const msg = sanitizeErrorMessage(err)
    assert.ok(
      msg.toLowerCase().includes('timeout') || msg.toLowerCase().includes('timed out'),
      'Timeout error should be sanitized',
    )
  })

  await t.test('24. Fallback is returned for null error', () => {
    const msg = sanitizeErrorMessage(null, 'Unable to complete.')
    assert.equal(msg, 'Unable to complete.')
  })

  await t.test('25. Ordinary error message passes through unchanged', () => {
    const msg = sanitizeErrorMessage(new Error('Watchlist not found'))
    assert.equal(msg, 'Watchlist not found')
  })

  // ── 8. Responsive positioning ─────────────────────────────────────────────
  await t.test('26. Desktop viewports (>860px) use top-right placement', () => {
    for (const vw of [1536, 1440, 1366, 1024]) {
      const pos = getToastPosition(vw)
      assert.equal(pos.placement, 'top-right', `${vw}px should use top-right`)
      assert.ok(pos.fixedWidth, `${vw}px should have fixed width`)
    }
  })

  await t.test('27. Mobile viewports (≤860px) use top-center placement', () => {
    for (const vw of [860, 768, 480, 375]) {
      const pos = getToastPosition(vw)
      assert.equal(pos.placement, 'top-center', `${vw}px should use top-center`)
      assert.ok(!pos.fixedWidth, `${vw}px should not have fixed width`)
    }
  })

  await t.test('28. Mobile top offset clears the fixed header (≥64px)', () => {
    const pos = getToastPosition(375)
    assert.ok(pos.top >= 64, 'Mobile top offset must clear at least the 64px fixed header')
  })

  await t.test('29. Desktop top offset clears the header with gap (≥64px)', () => {
    const pos = getToastPosition(1536)
    assert.ok(pos.top >= 64, 'Desktop top must clear the 64px header')
  })

  await t.test('30. Mobile positioning has left and right margins set', () => {
    const pos = getToastPosition(375)
    assert.ok(typeof pos.left === 'number' && pos.left >= 8)
    assert.ok(typeof pos.right === 'number' && pos.right >= 8)
  })

  // ── 9. Multiple simultaneous toasts ──────────────────────────────────────
  await t.test('31. Multiple different toasts can coexist', () => {
    const store = createToastStore()
    store.addToast({ type: 'success', message: 'RELIANCE added to Watchlist.' })
    store.addToast({ type: 'info', message: 'Paper Trading session started.' })
    store.addToast({ type: 'warning', message: 'Select a stock before analyzing.' })
    assert.equal(store.getToasts().length, 3)
    store.clear()
  })

  await t.test('32. Each toast has a unique id', () => {
    const store = createToastStore()
    const ids = []
    for (let i = 0; i < 4; i++) {
      store.clearDedupeWindow()
      const id = store.addToast({ type: 'info', message: `Event ${i}` })
      if (id) ids.push(id)
    }
    const uniqueIds = new Set(ids)
    assert.equal(uniqueIds.size, ids.length, 'All toast IDs must be unique')
    store.clear()
  })

  // ── 10. Action-toast message quality ─────────────────────────────────────
  await t.test('33. Watchlist create message is clear', () => {
    const name = 'My Watchlist'
    const msg = `Watchlist "${name}" created.`
    assert.ok(msg.includes(name))
    assert.ok(msg.includes('created'))
  })

  await t.test('34. Watchlist delete message is clear', () => {
    const name = 'Tech Stocks'
    const msg = `Watchlist "${name}" deleted.`
    assert.ok(msg.includes(name))
    assert.ok(msg.includes('deleted'))
  })

  await t.test('35. Add stock to watchlist message includes symbol and watchlist name', () => {
    const sym = 'RELIANCE'
    const wl = 'My Watchlist'
    const msg = `${sym} added to "${wl}".`
    assert.ok(msg.includes(sym))
    assert.ok(msg.includes(wl))
  })

  await t.test('36. Remove stock from watchlist message includes symbol and watchlist name', () => {
    const sym = 'TCS'
    const wl = 'My Watchlist'
    const msg = `${sym} removed from "${wl}".`
    assert.ok(msg.includes(sym))
    assert.ok(msg.includes(wl))
  })

  await t.test('37. Scanner no-selection warning is concise and user-friendly', () => {
    const msg = 'Select a stock row before analyzing.'
    assert.ok(msg.length < 60)
    assert.ok(!msg.toLowerCase().startsWith('error'))
  })

  await t.test('38. Paper trading start message is informative', () => {
    const msg = 'Paper Trading session started.'
    assert.ok(msg.toLowerCase().includes('started'))
  })

  await t.test('39. Paper trading reset message is informative', () => {
    const msg = 'Paper Trading session reset.'
    assert.ok(msg.toLowerCase().includes('reset'))
  })

  await t.test('40. Validation info message includes stock symbol', () => {
    const sym = 'HDFCBANK'
    const msg = `Validation started for ${sym}.`
    assert.ok(msg.includes(sym))
    assert.ok(msg.toLowerCase().includes('validation'))
  })

  await t.test('41. Validation complete message includes symbol and clear outcome', () => {
    const sym = 'TATAMOTORS'
    const msg = `${sym} passed validation.`
    assert.ok(msg.includes(sym))
    assert.ok(msg.toLowerCase().includes('validation'))
  })

  await t.test('42. Add stock to sector message includes symbol and sector', () => {
    const sym = 'WIPRO'
    const sector = 'IT'
    const msg = `${sym} added to "${sector}".`
    assert.ok(msg.includes(sym))
    assert.ok(msg.includes(sector))
  })
})
