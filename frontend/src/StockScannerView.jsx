import { useCallback, useEffect, useMemo, useState } from 'react'
import './StockScannerView.css'

const SIGNAL_FILTERS = ['ALL', 'BUY', 'SELL', 'NO TRADE']
const STATUS_FILTERS = ['ALL', 'VALIDATED', 'TESTING', 'FAILED']

function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '—'
  }

  return numeric.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatConfidence(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '—'
  }

  const percentage = numeric <= 1 ? numeric * 100 : numeric
  return `${Math.round(percentage)}%`
}

function formatTimestamp(value) {
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

function normalizeSignal(value) {
  const signal = String(value || '').toUpperCase().trim()

  if (signal === 'BUY') return 'BUY'
  if (signal === 'SELL') return 'SELL'
  return 'NO TRADE'
}

function normalizeStatus(value) {
  const status = String(value || '').toUpperCase().trim()

  if (status === 'VALIDATED') return 'VALIDATED'
  if (status === 'TESTING' || status === 'IN_PROGRESS') return 'TESTING'
  if (status === 'FAILED' || status === 'REJECTED') return 'FAILED'
  return status || 'PENDING'
}

function signalClass(signal) {
  if (signal === 'BUY') return 'scanner-signal-buy'
  if (signal === 'SELL') return 'scanner-signal-sell'
  return 'scanner-signal-neutral'
}

function statusClass(status) {
  if (status === 'VALIDATED') return 'scanner-status-validated'
  if (status === 'TESTING') return 'scanner-status-testing'
  if (status === 'FAILED') return 'scanner-status-failed'
  return 'scanner-status-pending'
}

function ScannerIcon({ type }) {
  const paths = {
    search: (
      <>
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    refresh: (
      <>
        <path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" />
        <path d="M21 3v5h-5" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 2.5 2.5L16 9" />
      </>
    ),
    alert: (
      <>
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <circle cx="12" cy="16" r="0.8" fill="currentColor" />
      </>
    ),
    chart: (
      <>
        <path d="M4 19V5" />
        <path d="M4 19h17" />
        <path d="m7 15 4-5 3 3 5-7" />
      </>
    ),
  }

  return (
    <svg
      className="scanner-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[type]}
    </svg>
  )
}

function ScannerStat({ label, value, tone = 'neutral' }) {
  return (
    <div className={`scanner-stat scanner-stat-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function StockScannerView() {
  const [scannerData, setScannerData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [signalFilter, setSignalFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const loadScanner = useCallback(async ({ manual = false } = {}) => {
    if (manual) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError(null)

    try {
      const response = await fetch('/api/stocks/scanner')

      if (!response.ok) {
        let message = `Scanner API returned HTTP ${response.status}`

        try {
          const body = await response.json()
          if (body?.detail) {
            message = body.detail
          }
        } catch {
          // Keep the HTTP status message.
        }

        throw new Error(message)
      }

      const payload = await response.json()
      setScannerData(payload)
    } catch (requestError) {
      setScannerData(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load the stock scanner.',
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadScanner()
    }, 0)

    return () => window.clearTimeout(timer)
  }, [loadScanner])

  const items = useMemo(
    () => (Array.isArray(scannerData?.items) ? scannerData.items : []),
    [scannerData],
  )

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase()

    return items.filter((item) => {
      const signal = normalizeSignal(item.signal)
      const status = normalizeStatus(item.validation_status)

      if (signalFilter !== 'ALL' && signal !== signalFilter) {
        return false
      }

      if (statusFilter !== 'ALL' && status !== statusFilter) {
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
      ].some((value) => String(value || '').toLowerCase().includes(query))
    })
  }, [items, search, signalFilter, statusFilter])

  const totalStocks = Number(scannerData?.total_stocks) || items.length
  const eligibleStocks = Number(scannerData?.signal_eligible_stocks) || 0
  const buyCount = Number(scannerData?.buy_count) || 0
  const sellCount = Number(scannerData?.sell_count) || 0
  const noTradeCount = Number(scannerData?.no_trade_count) || 0

  return (
    <div className="stock-scanner-view">
      <div className="scanner-breadcrumb">
        <div>
          <div className="scanner-eyebrow">MARKET WORKSPACE / SCANNER</div>
          <h1>Stock Scanner</h1>
          <p>
            NIFTY 50 constituents scanned through the SignalForge causal
            strategy engine.
          </p>
        </div>

        <button
          type="button"
          className={`scanner-refresh-btn ${refreshing ? 'is-refreshing' : ''}`}
          onClick={() => loadScanner({ manual: true })}
          disabled={loading || refreshing}
        >
          <ScannerIcon type="refresh" />
          <span>{refreshing ? 'Refreshing…' : 'Refresh Scanner'}</span>
        </button>
      </div>

      <div className="scanner-source-bar">
        <div className="scanner-source-left">
          <span className="scanner-live-dot" />
          <strong>Historical Scanner API</strong>
          <span>Local validated-data pipeline</span>
        </div>
        <span className="scanner-source-time">
          Latest evaluation: {formatTimestamp(scannerData?.timestamp)}
        </span>
      </div>

      {error && (
        <div className="scanner-error-banner">
          <ScannerIcon type="alert" />
          <div>
            <strong>Scanner unavailable</strong>
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => loadScanner({ manual: true })}>
            Retry
          </button>
        </div>
      )}

      <section className="scanner-stats-grid" aria-label="Scanner summary">
        <ScannerStat label="NIFTY 50 STOCKS" value={totalStocks} />
        <ScannerStat
          label="SIGNAL ELIGIBLE"
          value={eligibleStocks}
          tone="validated"
        />
        <ScannerStat label="BUY SIGNALS" value={buyCount} tone="buy" />
        <ScannerStat label="SELL SIGNALS" value={sellCount} tone="sell" />
        <ScannerStat
          label="NO TRADE"
          value={noTradeCount}
          tone="neutral"
        />
      </section>

      <section className="panel scanner-panel">
        <div className="scanner-panel-header">
          <div>
            <div className="scanner-section-label">SIGNAL MATRIX</div>
            <h2>All NIFTY 50 Constituents</h2>
          </div>
          <div className="scanner-count">
            Showing <strong>{filteredItems.length}</strong> of{' '}
            <strong>{items.length}</strong>
          </div>
        </div>

        <div className="scanner-controls">
          <label className="scanner-search">
            <ScannerIcon type="search" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search symbol, company, reason..."
              aria-label="Search scanner"
            />
          </label>

          <div className="scanner-filter-group">
            <span>Signal</span>
            <div className="scanner-filter-tabs">
              {SIGNAL_FILTERS.map((filter) => (
                <button
                  type="button"
                  key={filter}
                  className={signalFilter === filter ? 'active' : ''}
                  onClick={() => setSignalFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="scanner-filter-group">
            <span>Status</span>
            <div className="scanner-filter-tabs">
              {STATUS_FILTERS.map((filter) => (
                <button
                  type="button"
                  key={filter}
                  className={statusFilter === filter ? 'active' : ''}
                  onClick={() => setStatusFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="scanner-state">
            <div className="scanner-state-icon">
              <ScannerIcon type="chart" />
            </div>
            <strong>Loading NIFTY 50 scanner…</strong>
            <span>
              Reading real scanner results from the SignalForge backend.
            </span>
          </div>
        ) : error && items.length === 0 ? (
          <div className="scanner-state">
            <div className="scanner-state-icon">
              <ScannerIcon type="alert" />
            </div>
            <strong>Unable to load scanner results</strong>
            <span>Use Retry above after confirming the backend is running.</span>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="scanner-state">
            <div className="scanner-state-icon">
              <ScannerIcon type="search" />
            </div>
            <strong>No stocks match the current filters</strong>
            <span>Clear the search or choose ALL filters.</span>
          </div>
        ) : (
          <div className="scanner-table-wrap">
            <div className="scanner-table">
              <div className="scanner-table-head">
                <span>Stock</span>
                <span>Status</span>
                <span>Signal</span>
                <span>Price</span>
                <span>Score</span>
                <span>Confidence</span>
                <span>MTF</span>
                <span>Reason</span>
              </div>

              {filteredItems.map((item) => {
                const signal = normalizeSignal(item.signal)
                const status = normalizeStatus(item.validation_status)
                const eligible = Boolean(item.signal_eligible)

                return (
                  <div className="scanner-table-row" key={item.symbol}>
                    <div className="scanner-stock-cell">
                      <strong>{item.symbol}</strong>
                      <span>{item.name || 'NSE listed stock'}</span>
                      <small>{item.exchange || 'NSE'}</small>
                    </div>

                    <div className="scanner-status-cell">
                      <span className={`scanner-status ${statusClass(status)}`}>
                        {status}
                      </span>
                      <small>
                        {eligible ? 'Signal eligible' : 'Signals locked'}
                      </small>
                    </div>

                    <div className="scanner-signal-cell">
                      <span className={`scanner-signal ${signalClass(signal)}`}>
                        {signal}
                      </span>
                    </div>

                    <strong className="scanner-price">
                      {formatPrice(item.price)}
                    </strong>

                    <span className="scanner-number">
                      {Number.isFinite(Number(item.score))
                        ? Number(item.score).toFixed(2)
                        : '—'}
                    </span>

                    <span className="scanner-number">
                      {formatConfidence(item.confidence)}
                    </span>

                    <span className="scanner-number">
                      {item.timeframe_alignment || '—'}
                    </span>

                    <div className="scanner-reason">
                      <span>{item.reason || 'No strategy reason available.'}</span>
                      {item.timestamp && (
                        <small>{formatTimestamp(item.timestamp)}</small>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </section>

      <section className="scanner-disclosure panel">
        <div className="scanner-disclosure-icon">
          <ScannerIcon type="check" />
        </div>
        <div>
          <strong>Signal eligibility is validation-gated</strong>
          <p>
            Stocks that are not VALIDATED remain NO TRADE and do not generate
            fabricated signals. Adding a stock to a sector or watchlist does
            not approve it for trading signals.
          </p>
        </div>
      </section>
    </div>
  )
}

export default StockScannerView
