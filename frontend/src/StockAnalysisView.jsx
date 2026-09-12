import { useCallback, useEffect, useMemo, useState } from 'react'
import './StockAnalysisView.css'
import {
  addStockToWatchlist,
  fetchStock,
  fetchStockReadiness,
  fetchStockScanner,
  fetchStockValidation,
  fetchWatchlists,
  removeStockFromWatchlist,
  validateStock,
} from './api'
import { CandlestickChart, RsiChart } from './CandlestickChart'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import {
  formatAnalysisConfidence,
  formatAnalysisNumber,
  formatAnalysisPrice,
  formatAnalysisTimestamp,
  normalizeAnalysisSignal,
  normalizeAnalysisStatus,
} from './analysisUtils'
import {
  isEditableTarget,
  isModifierKey,
  findNextTimeframe,
} from './keyboardShortcuts'
import { useToast } from './useToast'
import { sanitizeErrorMessage } from './stateUtils'

const TIMEFRAMES = ['5m', '10m', '15m', '30m']

function StockAnalysisView({
  symbol: initialSymbol = 'RELIANCE',
  onBack,
  onSelectStock,
}) {
  const toast = useToast()
  const currentSymbol = (initialSymbol || 'RELIANCE').trim().toUpperCase()

  // Data states
  const [stockInfo, setStockInfo] = useState(null)
  const [scannerItem, setScannerItem] = useState(null)
  const [validationData, setValidationData] = useState(null)
  const [readinessData, setReadinessData] = useState(null)
  const [allStocks, setAllStocks] = useState([])

  // Watchlist integration state
  const [watchlists, setWatchlists] = useState([])
  const [watchlistLoading, setWatchlistLoading] = useState(false)

  // View & interaction states
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [validating, setValidating] = useState(false)

  // Chart states
  const [activeTimeframe, setActiveTimeframe] = useState('15m')
  const [chartViewRange, setChartViewRange] = useState(null)
  const [hoveredIndex, setHoveredIndex] = useState(null)
  const [hoveredCandle, setHoveredCandle] = useState(null)

  // ---------------------------------------------------------------------------
  // 1. Load Analysis Data for currentSymbol
  // ---------------------------------------------------------------------------
  const loadStockAnalysis = useCallback(
    async ({ manual = false } = {}) => {
      if (manual) {
        setRefreshing(true)
      } else {
        setLoading(true)
      }
      setError(null)

      // Clear previous chart state on reload/switch
      setChartViewRange(null)
      setHoveredIndex(null)
      setHoveredCandle(null)

      try {
        const [
          stockRes,
          scannerRes,
          valRes,
          readyRes,
          wlRes,
        ] = await Promise.allSettled([
          fetchStock(currentSymbol),
          fetchStockScanner(),
          fetchStockValidation(currentSymbol),
          fetchStockReadiness(currentSymbol),
          fetchWatchlists(),
        ])

        // Stock Base Info
        if (stockRes.status === 'fulfilled') {
          setStockInfo(stockRes.value)
        } else {
          setStockInfo(null)
        }

        // Scanner Item & Universe list
        if (scannerRes.status === 'fulfilled') {
          const items = Array.isArray(scannerRes.value?.items)
            ? scannerRes.value.items
            : []
          setAllStocks(items)

          const matched = items.find(
            (item) => String(item.symbol).toUpperCase() === currentSymbol,
          )
          setScannerItem(matched || null)
        } else {
          setScannerItem(null)
        }

        // Validation data
        if (valRes.status === 'fulfilled') {
          setValidationData(valRes.value)
        } else {
          setValidationData(null)
        }

        // Readiness data
        if (readyRes.status === 'fulfilled') {
          setReadinessData(readyRes.value)
        } else {
          setReadinessData(null)
        }

        // Watchlists
        if (wlRes.status === 'fulfilled') {
          setWatchlists(
            Array.isArray(wlRes.value?.watchlists) ? wlRes.value.watchlists : [],
          )
        }

        // Check if critical requests all failed
        if (
          stockRes.status === 'rejected' &&
          scannerRes.status === 'rejected' &&
          valRes.status === 'rejected'
        ) {
          const primaryErr =
            stockRes.reason?.message ||
            scannerRes.reason?.message ||
            'Unable to load stock analysis.'
          throw new Error(primaryErr)
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Unable to connect to SignalForge API.',
        )
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [currentSymbol],
  )

  useEffect(() => {
    Promise.resolve().then(() => {
      loadStockAnalysis()
    })
  }, [loadStockAnalysis])

  // ---------------------------------------------------------------------------
  // 2. Watchlist Action (Add / Remove)
  // ---------------------------------------------------------------------------
  const defaultWatchlist = useMemo(() => {
    if (!Array.isArray(watchlists) || watchlists.length === 0) return null
    return (
      watchlists.find((w) => w.name === 'My Watchlist') || watchlists[0]
    )
  }, [watchlists])

  const isInWatchlist = useMemo(() => {
    if (!defaultWatchlist || !Array.isArray(defaultWatchlist.stocks)) return false
    return defaultWatchlist.stocks.some(
      (s) =>
        String(s.symbol || s).toUpperCase() === currentSymbol,
    )
  }, [defaultWatchlist, currentSymbol])

  const handleToggleWatchlist = useCallback(async () => {
    if (!defaultWatchlist || watchlistLoading) return
    setWatchlistLoading(true)

    try {
      if (isInWatchlist) {
        await removeStockFromWatchlist(defaultWatchlist.name, currentSymbol)
        toast.success(`${currentSymbol} removed from "${defaultWatchlist.name}".`)
      } else {
        await addStockToWatchlist(defaultWatchlist.name, currentSymbol)
        toast.success(`${currentSymbol} added to "${defaultWatchlist.name}".`)
      }
      // Refresh watchlists state
      const updated = await fetchWatchlists()
      if (Array.isArray(updated?.watchlists)) {
        setWatchlists(updated.watchlists)
      }
    } catch (err) {
      toast.error(sanitizeErrorMessage(err, 'Unable to update watchlist.'))
    } finally {
      setWatchlistLoading(false)
    }
  }, [defaultWatchlist, watchlistLoading, isInWatchlist, currentSymbol, toast])

  // Analysis Keyboard Shortcuts
  useEffect(() => {
    const handleAnalysisKeyDown = (e) => {
      if (isEditableTarget(e.target)) return
      if (isModifierKey(e)) return

      // 'B' or 'b' -> Back to scanner
      if (e.key === 'b' || e.key === 'B') {
        e.preventDefault()
        if (typeof onBack === 'function') {
          onBack()
        }
        return
      }

      // 'W' or 'w' -> Toggle watchlist
      if (e.key === 'w' || e.key === 'W') {
        e.preventDefault()
        handleToggleWatchlist()
        return
      }

      // ArrowLeft -> previous timeframe
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        setActiveTimeframe((prev) => findNextTimeframe(prev, 'prev'))
        return
      }

      // ArrowRight -> next timeframe
      if (e.key === 'ArrowRight') {
        e.preventDefault()
        setActiveTimeframe((prev) => findNextTimeframe(prev, 'next'))
        return
      }
    }

    window.addEventListener('keydown', handleAnalysisKeyDown)
    return () => window.removeEventListener('keydown', handleAnalysisKeyDown)
  }, [onBack, handleToggleWatchlist])

  // ---------------------------------------------------------------------------
  // 3. Manual Re-Validation Action
  // ---------------------------------------------------------------------------
  const handleRunValidation = async () => {
    setValidating(true)
    try {
      const result = await validateStock(currentSymbol)
      setValidationData(result)
      const readiness = await fetchStockReadiness(currentSymbol)
      setReadinessData(readiness)
      toast.success(`${currentSymbol} validation complete.`, { title: 'Validation Done' })
    } catch (err) {
      toast.error(sanitizeErrorMessage(err, 'Validation request failed.'), { title: 'Validation Failed' })
    } finally {
      setValidating(false)
    }
  }

  // ---------------------------------------------------------------------------
  // 4. Stock Switcher
  // ---------------------------------------------------------------------------
  const handleSwitchStock = (newSymbol) => {
    if (!newSymbol || newSymbol === currentSymbol) return
    if (onSelectStock) {
      onSelectStock(newSymbol)
    }
  }

  // ---------------------------------------------------------------------------
  // Derived View Information
  // ---------------------------------------------------------------------------
  const companyName =
    stockInfo?.name || scannerItem?.name || `${currentSymbol} Equity`
  const exchange = stockInfo?.exchange || scannerItem?.exchange || 'NSE'
  const rawSignal = scannerItem?.signal || 'NO_TRADE'
  const signal = normalizeAnalysisSignal(rawSignal)
  const rawStatus =
    validationData?.status ||
    scannerItem?.validation_status ||
    stockInfo?.validation_status ||
    'INSUFFICIENT_DATA'
  const status = normalizeAnalysisStatus(rawStatus)
  const isEligible = Boolean(
    scannerItem?.signal_eligible ?? stockInfo?.signal_eligible,
  )

  const currentPrice =
    typeof scannerItem?.price === 'number'
      ? scannerItem.price
      : typeof stockInfo?.price === 'number'
        ? stockInfo.price
        : null

  const score = scannerItem?.score
  const confidence = scannerItem?.confidence
  const mtfAlignment = scannerItem?.timeframe_alignment
  const reason =
    scannerItem?.reason ||
    'No strategy setup currently identified for this instrument.'

  const passedGates = Array.isArray(validationData?.passed_gates)
    ? validationData.passed_gates
    : []
  const failedGates = Array.isArray(validationData?.failed_gates)
    ? validationData.failed_gates
    : []
  const issues = Array.isArray(validationData?.issues)
    ? validationData.issues
    : []

  const statusClass =
    status === 'VALIDATED'
      ? 'validated'
      : status === 'TESTING'
        ? 'testing'
        : status === 'REJECTED'
          ? 'rejected'
          : 'insufficient'

  const signalClass =
    signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'no-trade'

  // If loading initially with zero data
  if (loading && !stockInfo && !scannerItem && !validationData) {
    return (
      <div className="stock-analysis-view">
        <div className="analysis-nav-bar">
          <div className="analysis-breadcrumbs">
            {onBack && (
              <button
                type="button"
                className="analysis-back-btn"
                onClick={onBack}
                aria-label="Back to Stock Scanner"
              >
                ← Back to Scanner
              </button>
            )}
            <span className="analysis-bread-sep">/</span>
            <span className="analysis-bread-current">{currentSymbol}</span>
          </div>
        </div>
        <LoadingState
          title={`Loading Stock Analysis: ${currentSymbol}...`}
          description="Fetching market data, algorithmic signals, and validation gates from the backend..."
        />
      </div>
    )
  }

  // If hard error with zero data
  if (error && !stockInfo && !scannerItem && !validationData) {
    return (
      <div className="stock-analysis-view">
        <div className="analysis-nav-bar">
          <div className="analysis-breadcrumbs">
            {onBack && (
              <button
                type="button"
                className="analysis-back-btn"
                onClick={onBack}
                aria-label="Back to Stock Scanner"
              >
                ← Back to Scanner
              </button>
            )}
            <span className="analysis-bread-sep">/</span>
            <span className="analysis-bread-current">{currentSymbol}</span>
          </div>
        </div>
        <ErrorState
          title={`Analysis Unavailable for ${currentSymbol}`}
          message={error}
          onRetry={() => loadStockAnalysis()}
          retryLabel="Retry Analysis"
        />
      </div>
    )
  }

  // If backend returns empty / stock doesn't exist
  if (!stockInfo && !scannerItem && !validationData) {
    return (
      <div className="stock-analysis-view">
        <div className="analysis-nav-bar">
          <div className="analysis-breadcrumbs">
            {onBack && (
              <button
                type="button"
                className="analysis-back-btn"
                onClick={onBack}
                aria-label="Back to Stock Scanner"
              >
                ← Back to Scanner
              </button>
            )}
            <span className="analysis-bread-sep">/</span>
            <span className="analysis-bread-current">{currentSymbol}</span>
          </div>
        </div>
        <EmptyState
          title={`Stock ${currentSymbol} Not Found`}
          description="No instrument or strategy records exist for this symbol in the SignalForge universe."
          action={
            onBack ? (
              <button
                type="button"
                className="sf-state-retry-btn"
                onClick={onBack}
              >
                Return to Scanner
              </button>
            ) : null
          }
        />
      </div>
    )
  }

  return (
    <div className="stock-analysis-view">
      {/* 1. Header Navigation Bar */}
      <nav className="analysis-nav-bar" aria-label="Analysis navigation">
        <div className="analysis-breadcrumbs">
          {onBack && (
            <button
              type="button"
              className="analysis-back-btn"
              onClick={onBack}
              aria-label="Return to Stock Scanner"
            >
              ← Back to Scanner
            </button>
          )}
          <span className="analysis-bread-sep">/</span>
          <span className="analysis-bread-current">{currentSymbol} Analysis</span>
        </div>

        <div className="analysis-top-controls">
          {/* Quick Stock Switcher Dropdown */}
          {allStocks.length > 0 && (
            <div className="stock-switcher-wrap">
              <label htmlFor="stock-switcher" className="stock-switcher-label">
                Switch Stock:
              </label>
              <select
                id="stock-switcher"
                className="stock-switcher-select"
                value={currentSymbol}
                onChange={(e) => handleSwitchStock(e.target.value)}
                aria-label="Select stock to analyze"
              >
                {allStocks.map((stock) => (
                  <option key={stock.symbol} value={stock.symbol}>
                    {stock.symbol} — {stock.name || stock.symbol}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            className={`analysis-refresh-btn ${refreshing ? 'is-loading' : ''}`}
            onClick={() => loadStockAnalysis({ manual: true })}
            disabled={refreshing}
            aria-label="Refresh analysis data"
          >
            <span>{refreshing ? 'Refreshing…' : '↻ Refresh'}</span>
          </button>
        </div>
      </nav>

      {/* 2. Professional Stock Context Header */}
      <header className="stock-context-card" aria-label="Instrument details">
        <div className="stock-identity-group">
          <div className="stock-identity-row">
            <h1 className="stock-symbol-badge">{currentSymbol}</h1>
            <span className="stock-name-text">{companyName}</span>
            <span className="stock-exchange-tag">{exchange}</span>
          </div>

          <div className="stock-meta-tags-row">
            <span className={`stock-status-pill stock-status-${statusClass}`}>
              ● {status}
            </span>
            <span
              className={`stock-eligibility-tag ${isEligible ? 'is-eligible' : ''}`}
            >
              {isEligible ? '✓ Signal Eligible' : '✕ Signals Locked'}
            </span>
            {scannerItem?.timestamp && (
              <span className="text-muted small">
                Evaluated: {formatAnalysisTimestamp(scannerItem.timestamp)}
              </span>
            )}
          </div>
        </div>

        <div className="stock-context-metrics">
          <div className="stock-price-block">
            <span className="stock-price-label">Latest Price</span>
            <strong className="stock-price-val tabular-num">
              {formatAnalysisPrice(currentPrice)}
            </strong>
          </div>

          <div
            className={`stock-signal-badge ${signalClass}`}
            role="status"
            aria-label={`Current algorithmic signal: ${signal}`}
          >
            {signal}
          </div>

          {defaultWatchlist && (
            <button
              type="button"
              className={`stock-watchlist-btn ${isInWatchlist ? 'is-active' : ''}`}
              onClick={handleToggleWatchlist}
              disabled={watchlistLoading}
              aria-label={
                isInWatchlist
                  ? `Remove ${currentSymbol} from ${defaultWatchlist.name}`
                  : `Add ${currentSymbol} to ${defaultWatchlist.name}`
              }
            >
              <span>{isInWatchlist ? '★ In Watchlist' : '☆ Add to Watchlist'}</span>
            </button>
          )}
        </div>
      </header>

      {/* 3. Primary Analysis & Chart Grid */}
      <div className="analysis-main-grid">
        {/* Left Column: Interactive Candlestick Chart & RSI */}
        <section
          className="analysis-chart-panel"
          aria-label="Interactive trading chart"
        >
          <div className="analysis-chart-header">
            <div className="analysis-chart-title">
              <h2>{currentSymbol} Technical Chart</h2>
              {hoveredCandle && (
                <span className="text-muted small" style={{ marginLeft: '0.5rem' }}>
                  O: {formatAnalysisPrice(hoveredCandle.open)} H: {formatAnalysisPrice(hoveredCandle.high)} L: {formatAnalysisPrice(hoveredCandle.low)} C: {formatAnalysisPrice(hoveredCandle.close)}
                </span>
              )}
            </div>

            <div
              className="analysis-timeframe-tabs"
              role="tablist"
              aria-label="Select chart timeframe"
            >
              {TIMEFRAMES.map((tf) => (
                <button
                  type="button"
                  key={tf}
                  role="tab"
                  aria-selected={activeTimeframe === tf}
                  className={`analysis-timeframe-btn ${
                    activeTimeframe === tf ? 'is-active' : ''
                  }`}
                  onClick={() => {
                    setActiveTimeframe(tf)
                    setChartViewRange(null)
                    setHoveredIndex(null)
                    setHoveredCandle(null)
                  }}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Reusable Candlestick Chart Component */}
          <CandlestickChart
            symbol={currentSymbol}
            timeframe={activeTimeframe}
            signal={scannerItem}
            viewRange={chartViewRange}
            onViewRangeChange={setChartViewRange}
            hoverIndex={hoveredIndex}
            onHoverChange={(idx, candle) => {
              setHoveredIndex(idx)
              setHoveredCandle(candle)
            }}
          />

          {/* Reusable Real RSI (14) Indicator Chart */}
          <RsiChart
            symbol={currentSymbol}
            timeframe={activeTimeframe}
            viewRange={chartViewRange}
            hoverIndex={hoveredIndex}
            onHoverChange={(idx) => {
              setHoveredIndex(idx)
            }}
          />
        </section>

        {/* Right Column: Signal Decision & Metrics Card */}
        <aside
          className="analysis-decision-card"
          aria-label="Signal decision summary"
        >
          <span className="decision-card-tag">ALGORITHMIC STRATEGY DECISION</span>

          <div className={`decision-signal-dominant ${signalClass}`}>
            <span className="dominant-signal-text">{signal}</span>
            <span className="dominant-signal-sub">
              {signal === 'BUY'
                ? 'Bullish setup confirmed'
                : signal === 'SELL'
                  ? 'Bearish breakdown confirmed'
                  : 'No active trade setup'}
            </span>
          </div>

          <div className="decision-reason-box">
            <span>STRATEGY RATIONALE</span>
            <p>"{reason}"</p>
          </div>

          <div className="decision-stats-grid">
            <div className="decision-stat-box">
              <span>Score</span>
              <strong className="tabular-num">
                {formatAnalysisNumber(score)}
              </strong>
            </div>

            <div className="decision-stat-box">
              <span>Confidence</span>
              <strong className="tabular-num">
                {formatAnalysisConfidence(confidence)}
              </strong>
            </div>

            <div className="decision-stat-box">
              <span>MTF Alignment</span>
              <strong className="tabular-num">
                {mtfAlignment !== null && mtfAlignment !== undefined
                  ? `${mtfAlignment} / 4`
                  : '—'}
              </strong>
            </div>

            <div className="decision-stat-box">
              <span>Position</span>
              <strong className="tabular-num">
                {scannerItem?.position || 'FLAT'}
              </strong>
            </div>
          </div>
        </aside>
      </div>

      {/* 4. Secondary Grid: Validation Gates & Data Readiness */}
      <div className="analysis-secondary-grid">
        {/* Validation Pipeline Card */}
        <section
          className="analysis-info-card"
          aria-label="Stock validation status"
        >
          <div className="info-card-header">
            <h3>Validation Pipeline Status</h3>
            <span className={`stock-status-pill stock-status-${statusClass}`}>
              {status}
            </span>
          </div>

          <div className="validation-gates-list">
            <div className="gate-item">
              <span className="gate-name">Signal Eligibility</span>
              <span
                className={
                  isEligible ? 'gate-badge-pass' : 'gate-badge-fail'
                }
              >
                {isEligible ? 'Passed' : 'Locked'}
              </span>
            </div>

            {passedGates.map((gate) => (
              <div className="gate-item" key={gate}>
                <span className="gate-name">
                  {gate.replace(/_/g, ' ').toUpperCase()}
                </span>
                <span className="gate-badge-pass">Passed</span>
              </div>
            ))}

            {failedGates.map((gate) => (
              <div className="gate-item" key={gate}>
                <span className="gate-name">
                  {gate.replace(/_/g, ' ').toUpperCase()}
                </span>
                <span className="gate-badge-fail">Failed</span>
              </div>
            ))}
          </div>

          {issues.length > 0 && (
            <div className="validation-issues-box">
              <strong>Validation Issues:</strong>
              <ul>
                {issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            className="run-validate-btn"
            onClick={handleRunValidation}
            disabled={validating}
          >
            <span>{validating ? 'Running Validation…' : 'Run Full Validation'}</span>
          </button>
        </section>

        {/* Historical Data Readiness Card */}
        <section
          className="analysis-info-card"
          aria-label="Historical data readiness"
        >
          <div className="info-card-header">
            <h3>Historical Data Readiness</h3>
            <span className="text-muted small">1-Minute OHLCV</span>
          </div>

          <div className="readiness-stats-grid">
            <div className="readiness-stat-item">
              <span>Data Coverage</span>
              <strong>
                {readinessData?.covers_required_period
                  ? 'Covers Period'
                  : readinessData?.available
                    ? 'Available'
                    : 'Not Available'}
              </strong>
            </div>

            <div className="readiness-stat-item">
              <span>Total Records</span>
              <strong className="tabular-num">
                {readinessData?.total_rows
                  ? Number(readinessData.total_rows).toLocaleString('en-IN')
                  : '—'}
              </strong>
            </div>

            <div className="readiness-stat-item">
              <span>Earliest Timestamp</span>
              <strong className="tabular-num small">
                {formatAnalysisTimestamp(readinessData?.first_timestamp)}
              </strong>
            </div>

            <div className="readiness-stat-item">
              <span>Latest Timestamp</span>
              <strong className="tabular-num small">
                {formatAnalysisTimestamp(readinessData?.last_timestamp)}
              </strong>
            </div>
          </div>

          {readinessData?.path && (
            <div className="text-muted small" style={{ marginTop: '0.5rem' }}>
              <span>Storage path: </span>
              <code style={{ fontSize: '0.6875rem' }}>
                {readinessData.path}
              </code>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

export default StockAnalysisView
