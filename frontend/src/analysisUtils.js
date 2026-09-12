/**
 * Pure utility functions for the Stock Analysis workflow.
 *
 * Adheres strictly to SignalForge principles:
 * - Never invents prices, signals, scores, indicators, or predictions.
 * - Formats and normalizes only real data provided by the backend.
 * - Handles missing/null values safely and deterministically.
 */

/**
 * Format a stock price into Indian Rupee representation.
 *
 * @param {number|null|undefined} price
 * @returns {string}
 */
export function formatAnalysisPrice(price) {
  if (price === null || price === undefined || price === '') {
    return '—'
  }

  const numeric = typeof price === 'number' ? price : Number(price)
  if (Number.isNaN(numeric) || !Number.isFinite(numeric)) {
    return '—'
  }

  return `₹${numeric.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/**
 * Format an indicator or metric number with configurable decimals.
 *
 * @param {number|null|undefined} value
 * @param {number} decimals
 * @returns {string}
 */
export function formatAnalysisNumber(value, decimals = 2) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric) || !Number.isFinite(numeric)) {
    return '—'
  }

  return numeric.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * Format confidence value (0.0 - 1.0) into percentage string.
 *
 * @param {number|null|undefined} confidence
 * @returns {string}
 */
export function formatAnalysisConfidence(confidence) {
  if (confidence === null || confidence === undefined || confidence === '') {
    return '—'
  }

  const numeric = typeof confidence === 'number' ? confidence : Number(confidence)
  if (Number.isNaN(numeric) || !Number.isFinite(numeric)) {
    return '—'
  }

  const pct = numeric <= 1 ? numeric * 100 : numeric
  return `${pct.toFixed(1)}%`
}

/**
 * Format timestamp into standard IST string representation.
 *
 * @param {string|Date|null|undefined} timestamp
 * @returns {string}
 */
export function formatAnalysisTimestamp(timestamp) {
  if (!timestamp) {
    return '—'
  }

  let iso = String(timestamp).trim()
  if (!/[Z+-]\d{2}:?\d{2}$/.test(iso) && !iso.endsWith('Z')) {
    iso = `${iso}+05:30`
  }

  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return String(timestamp)
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(date)
}

/**
 * Calculate change and change percentage between two prices.
 *
 * @param {number|null|undefined} current
 * @param {number|null|undefined} previous
 * @returns {{ diff: number, pct: number, text: string, isUp: boolean } | null}
 */
export function calculatePriceChange(current, previous) {
  if (
    current === null ||
    current === undefined ||
    previous === null ||
    previous === undefined
  ) {
    return null
  }

  const currNum = typeof current === 'number' ? current : Number(current)
  const prevNum = typeof previous === 'number' ? previous : Number(previous)

  if (
    Number.isNaN(currNum) ||
    Number.isNaN(prevNum) ||
    prevNum <= 0
  ) {
    return null
  }

  const diff = currNum - prevNum
  const pct = (diff / prevNum) * 100
  const isUp = diff >= 0
  const prefix = isUp ? '+' : ''

  return {
    diff,
    pct,
    isUp,
    text: `${prefix}${diff.toFixed(2)} (${prefix}${pct.toFixed(2)}%)`,
  }
}

/**
 * Normalize raw backend signal value without reinterpretation.
 *
 * @param {string|null|undefined} signal
 * @returns {'BUY'|'SELL'|'NO TRADE'|string}
 */
export function normalizeAnalysisSignal(signal) {
  if (!signal) return 'NO TRADE'

  const normalized = String(signal).trim().toUpperCase()
  if (normalized === 'BUY') return 'BUY'
  if (normalized === 'SELL') return 'SELL'
  if (normalized === 'NO_TRADE' || normalized === 'NO TRADE') return 'NO TRADE'

  return normalized.replace(/_/g, ' ')
}

/**
 * Normalize raw backend status value.
 *
 * @param {string|null|undefined} status
 * @returns {string}
 */
export function normalizeAnalysisStatus(status) {
  if (!status) return 'INSUFFICIENT DATA'

  const normalized = String(status).trim().toUpperCase()
  if (normalized === 'VALIDATED' || normalized === 'APPROVED') return 'VALIDATED'
  if (normalized === 'TESTING' || normalized === 'IN_PROGRESS') return 'TESTING'
  if (normalized === 'REJECTED' || normalized === 'FAILED') return 'REJECTED'
  if (normalized === 'INSUFFICIENT_DATA') return 'INSUFFICIENT DATA'

  return normalized.replace(/_/g, ' ')
}

/**
 * Filter a stock list by search term across symbol and company name.
 *
 * @param {Array<Object>} stocks
 * @param {string} query
 * @returns {Array<Object>}
 */
export function filterStockList(stocks, query) {
  if (!Array.isArray(stocks)) return []
  const cleanQuery = String(query || '').trim().toLowerCase()
  if (!cleanQuery) return stocks

  return stocks.filter((stock) => {
    const symbol = String(stock?.symbol || '').toLowerCase()
    const name = String(stock?.name || '').toLowerCase()
    return symbol.includes(cleanQuery) || name.includes(cleanQuery)
  })
}
