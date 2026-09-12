/**
 * keyboardShortcuts.js — SignalForge Keyboard Shortcut System
 *
 * Centralized, safe browser keyboard handling and shortcut definitions.
 * Ignores keystrokes when typing in inputs/textareas/selects and avoids
 * intercepting standard browser shortcuts (Ctrl+C, Ctrl+V, Ctrl+A, F5, etc.).
 */

/**
 * Check if the event target is an interactive text/editable input element.
 * @param {EventTarget | null} target - DOM element receiving the event.
 * @returns {boolean} - True if target is an editable form element.
 */
export function isEditableTarget(target) {
  if (!target || typeof target !== 'object') return false

  const tagName = String(target.tagName || '').toUpperCase()
  if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT') {
    return true
  }

  if (target.isContentEditable) {
    return true
  }

  return false
}

/**
 * Check if the keyboard event involves standard modifier keys (Ctrl, Meta/Command, Alt).
 * Used to avoid hijacking browser shortcuts like Ctrl+C, Ctrl+V, Ctrl+R, etc.
 * @param {KeyboardEvent} event - Native keyboard event.
 * @returns {boolean} - True if Ctrl, Meta, or Alt is active.
 */
export function isModifierKey(event) {
  if (!event || typeof event !== 'object') return false
  return Boolean(event.ctrlKey || event.metaKey || event.altKey)
}

/**
 * Supported chart timeframes in order for keyboard cycling.
 */
export const TIMEFRAME_SEQUENCE = Object.freeze(['1m', '5m', '10m', '15m', '30m'])

/**
 * Cycle through supported chart timeframes using ArrowLeft / ArrowRight.
 * @param {string} current - Current timeframe (e.g. '15m').
 * @param {'next' | 'prev'} direction - Direction to cycle.
 * @returns {string} - Next timeframe.
 */
export function findNextTimeframe(current, direction = 'next') {
  const index = TIMEFRAME_SEQUENCE.indexOf(current)
  if (index === -1) return TIMEFRAME_SEQUENCE[0]

  if (direction === 'prev') {
    return index > 0
      ? TIMEFRAME_SEQUENCE[index - 1]
      : TIMEFRAME_SEQUENCE[TIMEFRAME_SEQUENCE.length - 1]
  }

  return index < TIMEFRAME_SEQUENCE.length - 1
    ? TIMEFRAME_SEQUENCE[index + 1]
    : TIMEFRAME_SEQUENCE[0]
}

/**
 * Navigation views mapped to number keys 1–7.
 */
export const NAVIGATION_SHORTCUTS = Object.freeze({
  '1': 'Dashboard',
  '2': 'Stock Scanner',
  '3': 'Stock Analysis',
  '4': 'Watchlists',
  '5': 'Sectors',
  '6': 'Paper Trading',
  '7': 'Validation',
})

/**
 * Categorized shortcut documentation registry for the UI help modal.
 */
export const SHORTCUT_GROUPS = Object.freeze([
  {
    category: 'Navigation',
    shortcuts: [
      { key: '1', description: 'Dashboard' },
      { key: '2', description: 'Stock Scanner' },
      { key: '3', description: 'Stock Analysis' },
      { key: '4', description: 'Watchlists' },
      { key: '5', description: 'Sectors' },
      { key: '6', description: 'Paper Trading' },
      { key: '7', description: 'Stock Validation' },
    ],
  },
  {
    category: 'Stock Scanner',
    shortcuts: [
      { key: '/', description: 'Focus search input' },
      { key: '↑ / ↓', description: 'Navigate stock rows' },
      { key: 'Enter / A', description: 'Analyze selected stock' },
      { key: 'W', description: 'Toggle stock in watchlist' },
      { key: 'Esc', description: 'Clear search / blur' },
    ],
  },
  {
    category: 'Stock Analysis',
    shortcuts: [
      { key: 'B', description: 'Back to Stock Scanner' },
      { key: 'W', description: 'Toggle stock in watchlist' },
      { key: '← / →', description: 'Cycle chart timeframe' },
    ],
  },
  {
    category: 'General',
    shortcuts: [
      { key: '?', description: 'Show keyboard shortcuts' },
      { key: 'Esc', description: 'Close dialog / cancel' },
    ],
  },
])
