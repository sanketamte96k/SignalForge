/**
 * SignalForge Stock Scanner Utilities
 * Pure helpers for filtering, sorting, formatting, and data normalization.
 */

export function formatScannerPrice(value) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '—'
  }

  return numeric.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function formatScannerConfidence(value) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '—'
  }

  const percentage = numeric <= 1 ? numeric * 100 : numeric
  return `${Math.round(percentage)}%`
}

export function formatScannerScore(value) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '—'
  }

  return numeric.toFixed(2)
}

export function formatScannerTimestamp(value) {
  if (!value) {
    return '—'
  }

  const raw = String(value).trim()
  let iso = raw

  if (!/[Z+-]\d{2}:?\d{2}$/.test(iso) && !iso.endsWith('Z')) {
    iso = `${iso}+05:30`
  }

  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return raw
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(date)
}

export function normalizeSignal(value) {
  const signal = String(value || '').toUpperCase().trim()

  if (signal === 'BUY') return 'BUY'
  if (signal === 'SELL') return 'SELL'
  return 'NO TRADE'
}

export function normalizeStatus(value) {
  const status = String(value || '').toUpperCase().trim()

  if (status === 'VALIDATED') return 'VALIDATED'
  if (status === 'TESTING' || status === 'IN_PROGRESS') return 'TESTING'
  if (status === 'FAILED' || status === 'REJECTED') return 'FAILED'
  return status || 'PENDING'
}

export function filterScannerItems(items, {
  search = '',
  signalFilter = 'ALL',
  statusFilter = 'ALL',
  eligibleOnly = false,
} = {}) {
  if (!Array.isArray(items)) {
    return []
  }

  const query = search.trim().toLowerCase()

  return items.filter((item) => {
    const signal = normalizeSignal(item.signal)
    const status = normalizeStatus(item.validation_status)
    const isEligible = Boolean(item.signal_eligible)

    if (signalFilter !== 'ALL' && signal !== signalFilter) {
      return false
    }

    if (statusFilter !== 'ALL' && status !== statusFilter) {
      return false
    }

    if (eligibleOnly && !isEligible) {
      return false
    }

    if (!query) {
      return true
    }

    return [
      item.symbol,
      item.name,
      item.exchange,
      item.reason,
      status,
      signal,
    ].some((val) => String(val || '').toLowerCase().includes(query))
  })
}

const SIGNAL_PRIORITY = { BUY: 1, SELL: 2, 'NO TRADE': 3 }
const STATUS_PRIORITY = { VALIDATED: 1, TESTING: 2, FAILED: 3, PENDING: 4 }

export function sortScannerItems(items, sortKey, sortDirection = 'asc') {
  if (!Array.isArray(items)) {
    return []
  }

  if (!sortKey) {
    return [...items]
  }

  const multiplier = sortDirection === 'desc' ? -1 : 1

  return [...items].sort((a, b) => {
    if (sortKey === 'symbol') {
      const symA = String(a.symbol || '').toUpperCase()
      const symB = String(b.symbol || '').toUpperCase()
      return symA.localeCompare(symB) * multiplier
    }

    if (sortKey === 'name') {
      const nameA = String(a.name || '').toUpperCase()
      const nameB = String(b.name || '').toUpperCase()
      return nameA.localeCompare(nameB) * multiplier
    }

    if (sortKey === 'status') {
      const pA = STATUS_PRIORITY[normalizeStatus(a.validation_status)] ?? 99
      const pB = STATUS_PRIORITY[normalizeStatus(b.validation_status)] ?? 99
      if (pA !== pB) return (pA - pB) * multiplier
      return String(a.symbol || '').localeCompare(String(b.symbol || ''))
    }

    if (sortKey === 'signal') {
      const pA = SIGNAL_PRIORITY[normalizeSignal(a.signal)] ?? 99
      const pB = SIGNAL_PRIORITY[normalizeSignal(b.signal)] ?? 99
      if (pA !== pB) return (pA - pB) * multiplier
      return String(a.symbol || '').localeCompare(String(b.symbol || ''))
    }

    if (sortKey === 'price' || sortKey === 'score' || sortKey === 'confidence' || sortKey === 'timeframe_alignment') {
      const valA = a[sortKey] !== null && a[sortKey] !== undefined ? Number(a[sortKey]) : null
      const valB = b[sortKey] !== null && b[sortKey] !== undefined ? Number(b[sortKey]) : null

      const isFiniteA = valA !== null && Number.isFinite(valA)
      const isFiniteB = valB !== null && Number.isFinite(valB)

      // Always push missing / null values to the end regardless of sort direction
      if (!isFiniteA && !isFiniteB) return 0
      if (!isFiniteA) return 1
      if (!isFiniteB) return -1

      if (valA !== valB) {
        return (valA - valB) * multiplier
      }

      return String(a.symbol || '').localeCompare(String(b.symbol || ''))
    }

    return 0
  })
}
