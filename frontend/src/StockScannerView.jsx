import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './StockScannerView.css'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import {
  fetchWatchlists,
  addStockToWatchlist,
  removeStockFromWatchlist,
} from './api'
import { isEditableTarget, isModifierKey } from './keyboardShortcuts'
import {
  formatScannerPrice,
  formatScannerConfidence,
  formatScannerScore,
  formatScannerTimestamp,
  normalizeSignal,
  normalizeStatus,
  filterScannerItems,
  sortScannerItems,
} from './scannerUtils'

const SIGNAL_FILTERS = ['ALL', 'BUY', 'SELL', 'NO TRADE']
const STATUS_FILTERS = ['ALL', 'VALIDATED', 'TESTING', 'FAILED']

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

function StockScannerView({ onSelectStock, focusTrigger = 0 }) {
  const searchInputRef = useRef(null)
  const [scannerData, setScannerData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [watchlistLoading, setWatchlistLoading] = useState(false)

  // Filter & Search states
  const [search, setSearch] = useState('')
  const [signalFilter, setSignalFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [eligibleOnly, setEligibleOnly] = useState(false)

  // Sorting & Row Selection
  const [sortKey, setSortKey] = useState('symbol')
  const [sortDirection, setSortDirection] = useState('asc')
  const [selectedSymbol, setSelectedSymbol] = useState(null)

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
    return filterScannerItems(items, {
      search,
      signalFilter,
      statusFilter,
      eligibleOnly,
    })
  }, [items, search, signalFilter, statusFilter, eligibleOnly])

  const processedItems = useMemo(() => {
    return sortScannerItems(filteredItems, sortKey, sortDirection)
  }, [filteredItems, sortKey, sortDirection])

  const handleSort = useCallback((key) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      if (['price', 'score', 'confidence', 'timeframe_alignment'].includes(key)) {
        setSortDirection('desc')
      } else {
        setSortDirection('asc')
      }
    }
  }, [sortKey])

  const handleResetFilters = useCallback(() => {
    setSearch('')
    setSignalFilter('ALL')
    setStatusFilter('ALL')
    setEligibleOnly(false)
    setSelectedSymbol(null)
    setSortKey('symbol')
    setSortDirection('asc')
  }, [])

  // Watchlist toggle handler
  const handleToggleWatchlist = useCallback(async (sym) => {
    if (!sym || watchlistLoading) return
    setWatchlistLoading(true)
    try {
      const wlData = await fetchWatchlists()
      const lists = Array.isArray(wlData?.watchlists) ? wlData.watchlists : []
      const defaultList = lists.find((w) => w.name === 'My Watchlist') || lists[0]
      if (!defaultList) return

      const isInList = Array.isArray(defaultList.stocks) && defaultList.stocks.some(
        (s) => String(s.symbol || s).toUpperCase() === sym.toUpperCase(),
      )

      if (isInList) {
        await removeStockFromWatchlist(defaultList.name, sym)
      } else {
        await addStockToWatchlist(defaultList.name, sym)
      }
    } catch {
      // Retain existing state on error
    } finally {
      setWatchlistLoading(false)
    }
  }, [watchlistLoading])

  // Focus search trigger from external navigation
  useEffect(() => {
    if (focusTrigger > 0 && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [focusTrigger])

  // Scanner Keyboard Shortcuts
  useEffect(() => {
    const handleScannerKeyDown = (e) => {
      // If typing in an editable field
      if (isEditableTarget(e.target)) {
        if (e.key === 'Escape') {
          if (search) {
            setSearch('')
          } else {
            searchInputRef.current?.blur()
          }
        }
        return
      }

      if (isModifierKey(e)) return

      // '/' focuses search
      if (e.key === '/') {
        e.preventDefault()
        searchInputRef.current?.focus()
        return
      }

      // 'ArrowDown' selects next row
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        if (processedItems.length === 0) return
        const idx = processedItems.findIndex((it) => it.symbol === selectedSymbol)
        if (idx === -1) {
          setSelectedSymbol(processedItems[0].symbol)
        } else {
          setSelectedSymbol(processedItems[Math.min(processedItems.length - 1, idx + 1)].symbol)
        }
        return
      }

      // 'ArrowUp' selects previous row
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        if (processedItems.length === 0) return
        const idx = processedItems.findIndex((it) => it.symbol === selectedSymbol)
        if (idx === -1) {
          setSelectedSymbol(processedItems[processedItems.length - 1].symbol)
        } else {
          setSelectedSymbol(processedItems[Math.max(0, idx - 1)].symbol)
        }
        return
      }

      // 'Enter' or 'A' or 'a' analyzes selected stock
      if (e.key === 'Enter' || e.key === 'a' || e.key === 'A') {
        if (selectedSymbol && onSelectStock) {
          e.preventDefault()
          onSelectStock(selectedSymbol)
        }
        return
      }

      // 'W' or 'w' toggles watchlist
      if (e.key === 'w' || e.key === 'W') {
        if (selectedSymbol) {
          e.preventDefault()
          handleToggleWatchlist(selectedSymbol)
        }
        return
      }
    }

    window.addEventListener('keydown', handleScannerKeyDown)
    return () => window.removeEventListener('keydown', handleScannerKeyDown)
  }, [processedItems, selectedSymbol, search, onSelectStock, handleToggleWatchlist])

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
          Latest evaluation: {formatScannerTimestamp(scannerData?.timestamp)}
        </span>
      </div>

      {error && (
        <div className="scanner-error-banner" role="alert">
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
          <div className="scanner-count" aria-live="polite">
            Showing <strong>{processedItems.length}</strong> of{' '}
            <strong>{items.length}</strong> stocks
            {processedItems.length < items.length && (
              <span className="scanner-filter-pill">
                ({items.length - processedItems.length} filtered)
              </span>
            )}
            {selectedSymbol && onSelectStock && (
              <button
                type="button"
                className="scanner-analyze-selected-btn"
                onClick={() => onSelectStock(selectedSymbol)}
                aria-label={`Open Stock Analysis for ${selectedSymbol}`}
              >
                Analyze {selectedSymbol} →
              </button>
            )}
          </div>
        </div>

        <div className="scanner-controls">
          <label className="scanner-search">
            <ScannerIcon type="search" />
            <input
              ref={searchInputRef}
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault()
                  if (search) {
                    setSearch('')
                  } else {
                    searchInputRef.current?.blur()
                  }
                }
              }}
              placeholder="Search symbol, company, reason..."
              aria-label="Search scanner by symbol, company, or reason"
            />
            {search && (
              <button
                type="button"
                className="scanner-search-clear-btn"
                onClick={() => setSearch('')}
                aria-label="Clear search input"
                title="Clear search"
              >
                ✕
              </button>
            )}
          </label>

          <div className="scanner-filter-group">
            <span>Signal</span>
            <div className="scanner-filter-tabs" role="group" aria-label="Signal filter">
              {SIGNAL_FILTERS.map((filter) => (
                <button
                  type="button"
                  key={filter}
                  className={signalFilter === filter ? 'active' : ''}
                  aria-pressed={signalFilter === filter}
                  onClick={() => setSignalFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="scanner-filter-group">
            <span>Status</span>
            <div className="scanner-filter-tabs" role="group" aria-label="Status filter">
              {STATUS_FILTERS.map((filter) => (
                <button
                  type="button"
                  key={filter}
                  className={statusFilter === filter ? 'active' : ''}
                  aria-pressed={statusFilter === filter}
                  onClick={() => setStatusFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="scanner-filter-group">
            <span>Eligibility</span>
            <div className="scanner-filter-tabs" role="group" aria-label="Eligibility filter">
              <button
                type="button"
                className={!eligibleOnly ? 'active' : ''}
                aria-pressed={!eligibleOnly}
                onClick={() => setEligibleOnly(false)}
                aria-label="Show all stocks"
              >
                ALL
              </button>
              <button
                type="button"
                className={eligibleOnly ? 'active' : ''}
                aria-pressed={eligibleOnly}
                onClick={() => setEligibleOnly(true)}
                aria-label="Show signal-eligible stocks only"
              >
                ELIGIBLE
              </button>
            </div>
          </div>
        </div>

        {loading && !scannerData ? (
          <LoadingState
            title="Loading NIFTY 50 Scanner..."
            description="Reading algorithmic scanner results from the SignalForge backend."
          />
        ) : error && items.length === 0 ? (
          <ErrorState
            title="Unable to Load Scanner Results"
            message={error}
            onRetry={() => loadScanner({ manual: true })}
            retryLabel="Retry Scanner"
          />
        ) : processedItems.length === 0 ? (
          <EmptyState
            title={items.length === 0 ? 'No Scanner Data Available' : 'No Stocks Match Current Filters'}
            description={
              items.length === 0
                ? 'The SignalForge scanner returned zero stock evaluation records.'
                : 'Try adjusting your search query, or reset the signal, status, and eligibility filters.'
            }
            action={
              search || signalFilter !== 'ALL' || statusFilter !== 'ALL' || eligibleOnly ? (
                <button
                  type="button"
                  className="sf-state-retry-btn"
                  onClick={handleResetFilters}
                >
                  Reset Filters
                </button>
              ) : (
                <button
                  type="button"
                  className="sf-state-retry-btn"
                  onClick={() => loadScanner({ manual: true })}
                >
                  Reload Scanner
                </button>
              )
            }
          />
        ) : (
          <div className="scanner-table-wrap">
            <div className="scanner-table" role="table" aria-label="NIFTY 50 Stock Scanner Results">
              <div className="scanner-table-head" role="row">
                <button
                  type="button"
                  className={`scanner-table-head-cell ${sortKey === 'symbol' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('symbol')}
                  role="columnheader"
                  aria-sort={sortKey === 'symbol' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Stock</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'symbol' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell ${sortKey === 'status' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('status')}
                  role="columnheader"
                  aria-sort={sortKey === 'status' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Status</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'status' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell ${sortKey === 'signal' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('signal')}
                  role="columnheader"
                  aria-sort={sortKey === 'signal' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Signal</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'signal' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell align-right ${sortKey === 'price' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('price')}
                  role="columnheader"
                  aria-sort={sortKey === 'price' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Price</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'price' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell align-right ${sortKey === 'score' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('score')}
                  role="columnheader"
                  aria-sort={sortKey === 'score' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Score</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'score' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell align-right ${sortKey === 'confidence' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('confidence')}
                  role="columnheader"
                  aria-sort={sortKey === 'confidence' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>Confidence</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'confidence' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <button
                  type="button"
                  className={`scanner-table-head-cell align-right ${sortKey === 'timeframe_alignment' ? 'is-sorted' : ''}`}
                  onClick={() => handleSort('timeframe_alignment')}
                  role="columnheader"
                  aria-sort={sortKey === 'timeframe_alignment' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <span>MTF</span>
                  <span className="scanner-sort-indicator" aria-hidden="true">
                    {sortKey === 'timeframe_alignment' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                  </span>
                </button>

                <span role="columnheader">Reason</span>
              </div>

              {processedItems.map((item) => {
                const signal = normalizeSignal(item.signal)
                const status = normalizeStatus(item.validation_status)
                const eligible = Boolean(item.signal_eligible)
                const isSelected = selectedSymbol === item.symbol

                return (
                  <div
                    className={`scanner-table-row ${isSelected ? 'is-selected' : ''}`}
                    key={item.symbol}
                    role="row"
                    tabIndex={0}
                    aria-selected={isSelected}
                    onClick={() => setSelectedSymbol(item.symbol)}
                    onDoubleClick={() => {
                      if (onSelectStock) {
                        onSelectStock(item.symbol)
                      }
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        if (onSelectStock) {
                          onSelectStock(item.symbol)
                        } else {
                          setSelectedSymbol((prev) => (prev === item.symbol ? null : item.symbol))
                        }
                      } else if (event.key === ' ') {
                        event.preventDefault()
                        setSelectedSymbol((prev) => (prev === item.symbol ? null : item.symbol))
                      }
                    }}
                  >
                    <div className="scanner-stock-cell" role="cell">
                      <strong>{item.symbol}</strong>
                      <span>{item.name || 'NSE listed stock'}</span>
                      <small>{item.exchange || 'NSE'}</small>
                    </div>

                    <div className="scanner-status-cell" role="cell">
                      <span className={`scanner-status ${statusClass(status)}`}>
                        {status}
                      </span>
                      <small>
                        {eligible ? 'Signal eligible' : 'Signals locked'}
                      </small>
                    </div>

                    <div className="scanner-signal-cell" role="cell">
                      <span className={`scanner-signal ${signalClass(signal)}`}>
                        {signal}
                      </span>
                    </div>

                    <strong className="scanner-price align-right" role="cell">
                      {formatScannerPrice(item.price)}
                    </strong>

                    <span className="scanner-number align-right" role="cell">
                      {formatScannerScore(item.score)}
                    </span>

                    <span className="scanner-number align-right" role="cell">
                      {formatScannerConfidence(item.confidence)}
                    </span>

                    <span className="scanner-number align-right" role="cell">
                      {item.timeframe_alignment ?? '—'}
                    </span>

                    <div className="scanner-reason" role="cell">
                      <div className="scanner-reason-inner">
                        <div className="scanner-reason-texts">
                          <span>{item.reason || 'No strategy reason available.'}</span>
                          {item.timestamp && (
                            <small>{formatScannerTimestamp(item.timestamp)}</small>
                          )}
                        </div>
                        {onSelectStock && (
                          <button
                            type="button"
                            className="scanner-row-analyze-btn"
                            onClick={(e) => {
                              e.stopPropagation()
                              onSelectStock(item.symbol)
                            }}
                            aria-label={`Analyze ${item.symbol}`}
                          >
                            Analyze →
                          </button>
                        )}
                      </div>
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
