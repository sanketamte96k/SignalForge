/**
 * settingsUtils.js — Centralized settings management and persistence for SignalForge.
 */

export const DEFAULT_SETTINGS = Object.freeze({
  // 1. General
  defaultTimeframe: '15m',
  autoRefresh: true,
  autoRefreshInterval: '30s',
  defaultLandingView: 'Dashboard',

  // 2. Chart Preferences
  showEma: true,
  showVolume: true,
  showRsi: true,
  crosshair: 'Normal', // 'Normal' | 'Magnet' | 'Hidden'
  defaultChartType: 'Candlestick', // 'Candlestick' | 'Line' | 'Bar' | 'Area'

  // 3. Notifications
  tradingSignalNotifications: true,
  validationWarnings: true,
  toastNotifications: true,

  // 4. Trading Preferences
  riskPerTrade: '1.0%', // '0.5%' | '1.0%' | '1.5%' | '2.0%' | '3.0%' | custom
  defaultPositionSize: 50000, // ₹50,000
  brokerageSlippage: '0.05%', // '0.03%' | '0.05%' | '0.10%'

  // 5. Interface
  compactInterface: false,
  sidebarBehavior: 'Expanded', // 'Expanded' | 'Auto-collapse' | 'Collapsed'
})

export const TIMEFRAME_OPTIONS = Object.freeze([
  '5m',
  '10m',
  '15m',
  '30m',
  '1H',
  '4H',
  '1D',
])

export const REFRESH_INTERVAL_OPTIONS = Object.freeze([
  { label: '10 seconds', value: '10s' },
  { label: '30 seconds', value: '30s' },
  { label: '60 seconds', value: '60s' },
  { label: '2 minutes', value: '2m' },
  { label: '5 minutes', value: '5m' },
])

export const LANDING_VIEW_OPTIONS = Object.freeze([
  'Dashboard',
  'NIFTY Analysis',
  'Stock Scanner',
  'Stock Analysis',
  'Sectors',
  'Watchlists',
  'Validation',
  'Paper Trading',
])

export const CHART_TYPE_OPTIONS = Object.freeze([
  'Candlestick',
  'Line',
  'Bar',
  'Area',
])

export const CROSSHAIR_OPTIONS = Object.freeze([
  { label: 'Normal', value: 'Normal', desc: 'Standard crosshair lines' },
  { label: 'Magnet', value: 'Magnet', desc: 'Snap crosshair to closest bar OHLC' },
  { label: 'Hidden', value: 'Hidden', desc: 'Hide crosshair pointer' },
])

export const RISK_OPTIONS = Object.freeze([
  '0.5%',
  '1.0%',
  '1.5%',
  '2.0%',
  '3.0%',
])

export const BROKERAGE_OPTIONS = Object.freeze([
  { label: '0.03% (Discount Broker)', value: '0.03%' },
  { label: '0.05% (Standard NSE Equity)', value: '0.05%' },
  { label: '0.10% (Conservative / High Slippage)', value: '0.10%' },
])

export const SIDEBAR_BEHAVIOR_OPTIONS = Object.freeze([
  { label: 'Expanded (Default)', value: 'Expanded' },
  { label: 'Auto-collapse on Select', value: 'Auto-collapse' },
  { label: 'Collapsed', value: 'Collapsed' },
])

const STORAGE_KEY = 'signalforge_settings'

/**
 * Safely loads user preferences from localStorage, falling back to DEFAULT_SETTINGS.
 * @returns {object} Current settings object
 */
export function loadSettings() {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return { ...DEFAULT_SETTINGS }
    }
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const parsed = JSON.parse(raw)
    return { ...DEFAULT_SETTINGS, ...parsed }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

/**
 * Safely saves user preferences to localStorage.
 * @param {object} settings - Settings object to persist
 * @returns {boolean} True if successfully stored
 */
export function saveSettings(settings) {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const merged = { ...DEFAULT_SETTINGS, ...settings }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
      applySettingsToDOM(merged)
      return true
    }
  } catch {
    // localStorage might be full or blocked
  }
  return false
}

/**
 * Resets user preferences in localStorage and returns fresh DEFAULT_SETTINGS.
 * @returns {object} Fresh default settings object
 */
export function resetSettings() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // ignore storage errors
  }
  const defaults = { ...DEFAULT_SETTINGS }
  applySettingsToDOM(defaults)
  return defaults
}

/**
 * Synchronizes layout settings with DOM classes/attributes for instant visual feedback.
 * @param {object} settings
 */
export function applySettingsToDOM(settings) {
  if (typeof document === 'undefined') return

  if (settings?.compactInterface) {
    document.documentElement.setAttribute('data-density', 'compact')
    document.body?.classList.add('sf-compact')
  } else {
    document.documentElement.setAttribute('data-density', 'comfortable')
    document.body?.classList.remove('sf-compact')
  }
}
