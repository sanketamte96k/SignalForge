import React, { useState, useEffect, useCallback } from 'react'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import {
  fetchOpenPaperTrades,
  createPaperTrade,
  closePaperTrade,
  updatePaperTrade,
  runBacktest,
  fetchBacktestJobStatus,
  fetchBacktestJobResult,
  getBacktestTearsheetUrl,
} from './api'
import { BacktestAnalyticsModal } from './BacktestAnalyticsModal'

function formatPrice(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—'
  }
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatNumber(value, decimals = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—'
  }
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function formatApiTimestamp(timestamp) {
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

function formatDuration(startTimestamp) {
  if (!startTimestamp) return '—'
  const start = new Date(startTimestamp).getTime()
  if (Number.isNaN(start)) return '—'
  const diffSec = Math.max(0, Math.floor((Date.now() - start) / 1000))
  if (diffSec < 60) return `${diffSec}s`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m`
  const diffHours = Math.floor(diffMin / 60)
  const remMin = diffMin % 60
  return `${diffHours}h ${remMin}m`
}

function PanelIcon({ type }) {
  if (type === 'check-small') {
    return (
      <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m5 12 4 4 10-10" />
      </svg>
    )
  }
  if (type === 'arrow-right') {
    return (
      <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </svg>
    )
  }
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <circle cx="12" cy="16" r="0.8" fill="currentColor" />
    </svg>
  )
}

export function StrategySignalPanel({
  signalData = null,
  latestData = null,
  loading = false,
  error = null,
  activeTimeframe = '15m',
  isUnsupported = false,
  onSelectTimeframe = null,
  onRetry = null,
  onNavigateFullAnalysis = null,
  onTradeCreated = null,
  onTradeClosed = null,
}) {
  const isHistorical = signalData?.status === 'HISTORICAL' || !signalData?.status
  const badgeType = loading
    ? 'loading'
    : error && !signalData
      ? 'error'
      : isHistorical
        ? 'historical'
        : 'live'

  const badgeText = loading
    ? 'Connecting'
    : error && !signalData
      ? 'API Unavailable'
      : isHistorical
        ? 'Historical API'
        : 'Live API'

  // Extract real signal
  const rawSignal = String(signalData?.signal || '').toUpperCase().trim()
  let displaySignal = '—'
  let signalSubtitle = 'NO ACTIVE TRADE SETUP'
  let signalClass = 'no-trade'

  if (rawSignal === 'BUY') {
    displaySignal = 'BUY'
    signalSubtitle = 'BUY SIGNAL FROM STRATEGY ENGINE'
    signalClass = 'buy'
  } else if (rawSignal === 'SELL') {
    displaySignal = 'SELL'
    signalSubtitle = 'SELL SIGNAL FROM STRATEGY ENGINE'
    signalClass = 'sell'
  } else if (rawSignal === 'NO_TRADE') {
    displaySignal = 'NO TRADE'
    signalSubtitle = 'NO ACTIVE TRADE SETUP'
    signalClass = 'no-trade'
  } else if (rawSignal) {
    displaySignal = rawSignal.replace(/_/g, ' ')
    signalSubtitle = 'STRATEGY ENGINE STATE'
    signalClass = 'no-trade'
  }

  const currentPrice =
    typeof signalData?.price === 'number'
      ? signalData.price
      : typeof latestData?.close === 'number'
        ? latestData.close
        : null

  const displayPrice =
    currentPrice !== null ? `₹${formatPrice(currentPrice)}` : '—'

  const rawTimestamp = signalData?.timestamp || latestData?.timestamp || null
  const displayTimestamp = rawTimestamp ? formatApiTimestamp(rawTimestamp) : '—'
  const displayReason = signalData?.signal_reason || '—'
  const timeframe = signalData?.timeframe || activeTimeframe
  const symbol = signalData?.symbol || 'NIFTY 50'

  // Confirmation factors
  const emaConfirmed = signalData?.confirmation?.ema === true
  const rsiConfirmed = signalData?.confirmation?.rsi_momentum === true
  const volumeConfirmed = signalData?.confirmation?.volume === true
  const mtfConfirmed = signalData?.confirmation?.multi_timeframe === true

  const confirmationStatus =
    rawSignal === 'BUY' || rawSignal === 'SELL'
      ? emaConfirmed && rsiConfirmed && mtfConfirmed
        ? 'Confirmed'
        : 'Partial'
      : 'No Trade'

  // Execution brackets calculation
  const hasBrackets =
    (rawSignal === 'BUY' || rawSignal === 'SELL') &&
    typeof signalData?.stop_loss === 'number' &&
    typeof signalData?.entry_price === 'number'

  const entryPrice = signalData?.entry_price ?? null
  const stopLoss = signalData?.stop_loss ?? null
  const target1 = signalData?.target_1 ?? null
  const target2 = signalData?.target_2 ?? null

  const slPctText =
    hasBrackets && stopLoss !== null && entryPrice !== null
      ? `${(((stopLoss - entryPrice) / entryPrice) * 100).toFixed(2)}%`
      : 'No active setup'

  const t1PctText =
    hasBrackets && target1 !== null && entryPrice !== null
      ? `+${(((target1 - entryPrice) / entryPrice) * 100).toFixed(2)}%`
      : 'No active setup'

  const t2PctText =
    hasBrackets && target2 !== null && entryPrice !== null
      ? `+${(((target2 - entryPrice) / entryPrice) * 100).toFixed(2)}%`
      : 'No active setup'

  // -------------------------------------------------------------------------
  // Phase 17: Interactive Paper Trading State & Actions
  // -------------------------------------------------------------------------
  const [activeTrade, setActiveTrade] = useState(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [orderQuantity, setOrderQuantity] = useState(1)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)

  // -------------------------------------------------------------------------
  // Phase 24G.28: Asynchronous Backtest Job Bridge State
  // -------------------------------------------------------------------------
  const [backtestStartDate, setBacktestStartDate] = useState('2023-01-01')
  const [backtestEndDate, setBacktestEndDate] = useState('2023-03-31')
  const [backtestExecutionModel, setBacktestExecutionModel] = useState('next_open')
  const [backtestInitialCapital, setBacktestInitialCapital] = useState(100000)
  const [backtestJobId, setBacktestJobId] = useState(null)
  const [backtestStatus, setBacktestStatus] = useState('IDLE')
  const [backtestProgress, setBacktestProgress] = useState(0)
  const [backtestError, setBacktestError] = useState(null)
  const [backtestResult, setBacktestResult] = useState(null)
  const [backtestSubmitting, setBacktestSubmitting] = useState(false)
  const [cancellingBacktest, setCancellingBacktest] = useState(false)
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false)

  const handleTriggerBacktest = async () => {
    if (backtestSubmitting || backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING') {
      return
    }

    if ((symbol === 'NIFTY 50' || symbol === 'NIFTY' || symbol === '^NSEI') && ((backtestStartDate && backtestStartDate > '2024-03-26') || (backtestEndDate && backtestEndDate > '2024-03-26'))) {
      setBacktestError('NIFTY 50 historical backtest date exceeds verified dataset boundary. Maximum permitted date is 2024-03-26.')
      return
    }

    if (backtestInitialCapital <= 0) {
      setBacktestError('Initial capital must be greater than zero.')
      return
    }

    setBacktestSubmitting(true)
    setBacktestError(null)
    setBacktestResult(null)
    setBacktestStatus('QUEUED')
    setBacktestProgress(0)

    try {
      const created = await runBacktest({
        symbol,
        start_date: backtestStartDate || undefined,
        end_date: backtestEndDate || undefined,
        initial_capital: Number(backtestInitialCapital),
        execution_model: backtestExecutionModel,
      })
      setBacktestJobId(created.job_id)
      setBacktestStatus(created.status || 'QUEUED')
    } catch (err) {
      setBacktestError(err.message || 'Failed to submit backtest job.')
      setBacktestStatus('FAILED')
    } finally {
      setBacktestSubmitting(false)
    }
  }

  const handleCancelBacktest = async () => {
    if (!backtestJobId || (backtestStatus !== 'QUEUED' && backtestStatus !== 'RUNNING')) {
      return
    }
    setCancellingBacktest(true)
    try {
      await cancelBacktestJob(backtestJobId)
      setBacktestStatus('CANCELLED')
      setBacktestError('Backtest job cancelled by user.')
    } catch (err) {
      setBacktestError(`Failed to cancel backtest job: ${err.message}`)
    } finally {
      setCancellingBacktest(false)
    }
  }

  useEffect(() => {
    if (!backtestJobId || (backtestStatus !== 'QUEUED' && backtestStatus !== 'RUNNING')) {
      return
    }

    let isMounted = true
    let consecutiveNetworkErrors = 0
    const interval = setInterval(async () => {
      try {
        const statusRes = await fetchBacktestJobStatus(backtestJobId)
        if (!isMounted) return

        consecutiveNetworkErrors = 0
        setBacktestStatus(statusRes.status)
        setBacktestProgress(statusRes.progress || 0)

        if (statusRes.status === 'COMPLETED') {
          clearInterval(interval)
          try {
            const resultRes = await fetchBacktestJobResult(backtestJobId)
            if (isMounted) {
              setBacktestResult(resultRes)
            }
          } catch (resErr) {
            if (isMounted) {
              setBacktestError(`Failed to fetch completed results: ${resErr.message}`)
            }
          }
        } else if (statusRes.status === 'FAILED') {
          clearInterval(interval)
          setBacktestError(statusRes.error || 'Backtest job execution failed.')
        } else if (statusRes.status === 'CANCELLED') {
          clearInterval(interval)
          setBacktestError('Backtest job was cancelled.')
        }
      } catch (pollErr) {
        if (!isMounted) return
        const errMsg = String(pollErr?.message || '')
        // Server restart detection: HTTP 404 indicates job was lost from memory
        if (errMsg.includes('404') || errMsg.toLowerCase().includes('not found')) {
          clearInterval(interval)
          setBacktestStatus('FAILED')
          setBacktestError('Job no longer found on server (server may have restarted). Please resubmit.')
          return
        }

        consecutiveNetworkErrors += 1
        if (consecutiveNetworkErrors >= 5) {
          clearInterval(interval)
          setBacktestStatus('FAILED')
          setBacktestError('Connection lost while polling backtest progress. Please verify backend status.')
        }
      }
    }, 1000)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [backtestJobId, backtestStatus])

  // Query active open paper trades for this symbol + timeframe
  const refreshActiveTrade = useCallback(async () => {
    try {
      const openTrades = await fetchOpenPaperTrades()
      if (Array.isArray(openTrades)) {
        const match = openTrades.find(
          (t) =>
            t.symbol === symbol &&
            t.timeframe === timeframe &&
            (t.status === 'OPEN' || t.status === 'TARGET_1_HIT'),
        )
        setActiveTrade(match || null)
      }
    } catch {
      // Ignore background fetch error
    }
  }, [symbol, timeframe])

  useEffect(() => {
    refreshActiveTrade()
  }, [refreshActiveTrade])

  // Handle Trade Execution
  const handleConfirmPaperTrade = async () => {
    if (isHistorical || symbol === 'NIFTY 50' || symbol === 'NIFTY' || symbol === '^NSEI') {
      setActionError('Paper trading unavailable: historical market data only. Latest available data: 26 Mar 2024.')
      return
    }

    if (orderQuantity <= 0 || !Number.isInteger(orderQuantity)) {
      setActionError('Quantity must be an integer > 0')
      return
    }
    if (!entryPrice || !stopLoss || !target1 || !target2) {
      setActionError('Incomplete strategy brackets. Cannot open paper trade.')
      return
    }

    setActionLoading(true)
    setActionError(null)
    setActionSuccess(null)

    try {
      const created = await createPaperTrade({
        symbol,
        side: rawSignal === 'BUY' ? 'LONG' : 'SHORT',
        timeframe,
        entry_price: entryPrice,
        stop_loss: stopLoss,
        target_1: target1,
        target_2: target2,
        quantity: orderQuantity,
        signal_price: currentPrice || entryPrice,
        strategy_signal: rawSignal,
      })
      setActiveTrade(created)
      setShowConfirmModal(false)
      setActionSuccess(`Paper trade ${created.trade_id} opened successfully!`)
      if (onTradeCreated) onTradeCreated(created)
    } catch (err) {
      setActionError(err.message || 'Failed to open paper trade')
    } finally {
      setActionLoading(false)
    }
  }

  // Handle Trade Manual Close
  const handleClosePaperTrade = async () => {
    if (!activeTrade) return

    setActionLoading(true)
    setActionError(null)
    setActionSuccess(null)

    try {
      const closed = await closePaperTrade(activeTrade.trade_id, {
        exit_price: currentPrice || activeTrade.entry_price,
        reason: 'MANUAL_CLOSE',
      })
      setActiveTrade(null)
      setActionSuccess(`Paper trade closed at ₹${formatPrice(closed.exit_price)}. Realized P&L: ₹${formatPrice(closed.realized_pnl)}`)
      if (onTradeClosed) onTradeClosed(closed)
    } catch (err) {
      setActionError(err.message || 'Failed to close paper trade')
    } finally {
      setActionLoading(false)
    }
  }

  // Calculate live unrealized P&L for display
  const liveUnrealizedPnl =
    activeTrade && typeof currentPrice === 'number'
      ? activeTrade.side === 'LONG'
        ? (currentPrice - activeTrade.entry_price) * activeTrade.quantity
        : (activeTrade.entry_price - currentPrice) * activeTrade.quantity
      : activeTrade?.unrealized_pnl ?? 0.0

  return (
    <div className="signal-panel panel" aria-label="Strategy Signal Panel">
      <div className="panel-header signal-panel-header">
        <div className="signal-header-left">
          <h2>{symbol} • Strategy Signal</h2>
        </div>
        <div className="signal-header-right">
          <span className={`signal-live-badge ${badgeType}`}>
            <span className={`signal-badge-dot ${badgeType}`} />
            {badgeText}
          </span>
          <span
            className={`signal-tf-tag ${isUnsupported ? 'warning' : 'active'}`}
            title={`Active strategy timeframe: ${timeframe}`}
          >
            {isUnsupported ? 'Unsupported' : timeframe}
          </span>
        </div>
      </div>

      <div className="signal-content">
        {loading && !signalData ? (
          <LoadingState
            title="Connecting to Strategy Engine..."
            description="Fetching real-time algorithmic signal and price updates..."
            compact
          />
        ) : isUnsupported ? (
          <EmptyState
            title={`Timeframe ${activeTimeframe} Not Supported`}
            description="The SignalForge multi-timeframe strategy engine operates on 5m, 10m, 15m, and 30m intervals. Higher timeframes are not evaluated by the causal engine."
            action={
              <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                <button
                  type="button"
                  className="sf-state-retry-btn"
                  onClick={() => onSelectTimeframe && onSelectTimeframe('15m')}
                >
                  Switch to 15m
                </button>
                <button
                  type="button"
                  className="sf-state-retry-btn"
                  onClick={() => onSelectTimeframe && onSelectTimeframe('5m')}
                >
                  Switch to 5m
                </button>
              </div>
            }
            compact
          />
        ) : error && !signalData ? (
          <ErrorState
            title="Signal Engine Offline"
            message={error}
            onRetry={onRetry}
            retryLabel="Retry Connection"
            compact
          />
        ) : !signalData ? (
          <EmptyState
            title="Strategy Data Unavailable"
            description="No strategy state was returned by the engine."
            action={
              <button
                type="button"
                className="sf-state-retry-btn"
                onClick={onRetry}
              >
                Retry
              </button>
            }
            compact
          />
        ) : (
          <>
            {/* 1. Visually Dominant BUY / SELL / NO TRADE status */}
            <div className="signal-badge-section">
              <div className="signal-tag-label">ALGORITHMIC SIGNAL</div>
              <div className={`signal-dominant-box ${signalClass}`}>
                <div className="signal-dominant-text">{displaySignal}</div>
                <div className="signal-dominant-sub">{signalSubtitle}</div>
              </div>
            </div>

            {/* 2. Key Instrument & Price Metrics */}
            <div className="signal-metrics-list">
              <div className="signal-metric-row">
                <span className="detail-muted">Instrument</span>
                <strong className="instrument-title">{symbol}</strong>
              </div>
              <div className="signal-metric-row">
                <span className="detail-muted">{isHistorical ? 'HISTORICAL CLOSE' : 'Current Price'}</span>
                <strong className="numeric-val tabular-num">
                  {displayPrice}
                  {isHistorical && rawTimestamp && (
                    <span style={{ fontSize: '11px', fontWeight: 'normal', color: '#88a3b8', marginLeft: '6px' }}>
                      ({displayTimestamp})
                    </span>
                  )}
                </strong>
              </div>
              <div className="signal-metric-row">
                <span className="detail-muted">Signal Timestamp</span>
                <strong className="numeric-val tabular-num">
                  {displayTimestamp}
                </strong>
              </div>
              <div className="signal-metric-row">
                <span className="detail-muted">Signal Timeframe</span>
                <strong className="timeframe-tag positive">{timeframe}</strong>
              </div>
              <div className="signal-metric-row">
                <span className="detail-muted">Signal Reason</span>
                <strong className="reason-val">{displayReason}</strong>
              </div>
              {typeof signalData.confidence === 'number' && (
                <div className="signal-metric-row">
                  <span className="detail-muted">Confidence</span>
                  <strong className="confidence-val tabular-num">
                    {signalData.confidence}%
                  </strong>
                </div>
              )}
            </div>

            {/* 3. Confirmation Factors */}
            <div className="confirmation-section">
              <div className="confirmation-header">
                <span className="detail-muted-title">CONFIRMATION FACTORS</span>
                <span
                  className={`confirmation-status-pill ${confirmationStatus === 'Confirmed'
                      ? 'confirmed'
                      : confirmationStatus === 'Partial'
                        ? 'partial'
                        : 'neutral'
                    }`}
                >
                  {confirmationStatus}
                </span>
              </div>

              <div className="factor-list">
                <div
                  className={`factor-item ${emaConfirmed ? 'factor-confirmed' : 'factor-neutral'
                    }`}
                >
                  <span className="factor-icon-wrap">
                    <PanelIcon
                      type={emaConfirmed ? 'check-small' : 'alert-circle'}
                    />
                  </span>
                  <div className="factor-text">
                    <strong>EMA Confirmation</strong>
                    <span>
                      {signalData.indicators?.ema_fast != null
                        ? `EMA20: ${formatNumber(signalData.indicators.ema_fast)} • EMA50: ${formatNumber(signalData.indicators.ema_slow)}`
                        : 'Evaluating causal EMA20 vs EMA50 trend'}
                    </span>
                  </div>
                </div>

                <div
                  className={`factor-item ${rsiConfirmed ? 'factor-confirmed' : 'factor-neutral'
                    }`}
                >
                  <span className="factor-icon-wrap">
                    <PanelIcon
                      type={rsiConfirmed ? 'check-small' : 'alert-circle'}
                    />
                  </span>
                  <div className="factor-text">
                    <strong>RSI + Momentum</strong>
                    <span>
                      {signalData.indicators?.rsi != null
                        ? `RSI(14): ${formatNumber(signalData.indicators.rsi)} (${rsiConfirmed ? 'Momentum supported' : 'Momentum unconfirmed'})`
                        : 'Evaluating causal RSI(14) momentum'}
                    </span>
                  </div>
                </div>

                <div
                  className={`factor-item ${volumeConfirmed ? 'factor-confirmed' : 'factor-neutral'
                    }`}
                >
                  <span className="factor-icon-wrap">
                    <PanelIcon
                      type={volumeConfirmed ? 'check-small' : 'alert-circle'}
                    />
                  </span>
                  <div className="factor-text">
                    <strong>Volume Confirmation</strong>
                    <span>
                      {signalData.confirmation?.volume === null
                        ? 'RVOL unavailable for index data'
                        : volumeConfirmed
                          ? 'Volume support confirmed'
                          : 'Insufficient volume support'}
                    </span>
                  </div>
                </div>

                <div
                  className={`factor-item ${mtfConfirmed ? 'factor-confirmed' : 'factor-neutral'
                    }`}
                >
                  <span className="factor-icon-wrap">
                    <PanelIcon
                      type={mtfConfirmed ? 'check-small' : 'alert-circle'}
                    />
                  </span>
                  <div className="factor-text">
                    <strong>Multi-Timeframe Alignment</strong>
                    <span>
                      {mtfConfirmed
                        ? '4/4 timeframes aligned (5m, 10m, 15m, 30m)'
                        : 'Disagreement across evaluated timeframes'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 4. Execution Targets & Stop Loss */}
            <div className="trade-levels-section">
              <span className="detail-muted-title">
                EXECUTION TARGETS & STOP LOSS
              </span>
              <div className="trade-levels-grid">
                <div className="trade-level-card sl">
                  <div className="level-badge sl-badge">SL</div>
                  <div className="level-info">
                    <span className="level-title">Stop Loss</span>
                    <strong className="negative tabular-num">
                      {stopLoss !== null ? `₹${formatPrice(stopLoss)}` : '—'}
                    </strong>
                    <span className="level-pct negative tabular-num">
                      {slPctText}
                    </span>
                  </div>
                </div>

                <div className="trade-level-card t1">
                  <div className="level-badge t1-badge">T1</div>
                  <div className="level-info">
                    <span className="level-title">Target 1</span>
                    <strong className="positive tabular-num">
                      {target1 !== null ? `₹${formatPrice(target1)}` : '—'}
                    </strong>
                    <span className="level-pct positive tabular-num">
                      {t1PctText}
                    </span>
                  </div>
                </div>

                <div className="trade-level-card t2">
                  <div className="level-badge t2-badge">T2</div>
                  <div className="level-info">
                    <span className="level-title">Target 2</span>
                    <strong className="positive tabular-num">
                      {target2 !== null ? `₹${formatPrice(target2)}` : '—'}
                    </strong>
                    <span className="level-pct positive tabular-num">
                      {t2PctText}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* ---------------------------------------------------------------
                Phase 17: Interactive Paper Trading Panel Section
                --------------------------------------------------------------- */}
            <div className="paper-trade-panel-section" style={{ marginTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span className="detail-muted-title">PAPER TRADING ENGINE</span>
                <span className="paper-sim-badge" style={{ fontSize: '9px', padding: '2px 6px', background: 'rgba(255, 179, 0, 0.15)', color: '#ffb300', border: '1px solid rgba(255, 179, 0, 0.4)', borderRadius: '3px', fontWeight: 'bold' }}>
                  SIMULATED • NO REAL ORDER
                </span>
              </div>

              {actionError && (
                <div style={{ padding: '6px 8px', background: 'rgba(255, 79, 94, 0.15)', border: '1px solid #ff4f5e', borderRadius: '4px', color: '#ff6876', fontSize: '11px', marginBottom: '8px' }}>
                  {actionError}
                </div>
              )}

              {actionSuccess && (
                <div style={{ padding: '6px 8px', background: 'rgba(0, 217, 163, 0.15)', border: '1px solid #00d9a3', borderRadius: '4px', color: '#00eaaf', fontSize: '11px', marginBottom: '8px' }}>
                  {actionSuccess}
                </div>
              )}

              {/* Case A: Active Open Paper Trade */}
              {activeTrade ? (
                <div className="paper-open-position-card" style={{ background: 'rgba(7, 26, 45, 0.8)', border: '1px solid #00d9a3', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      <span style={{ fontWeight: 'bold', fontSize: '12px', color: activeTrade.side === 'LONG' ? '#00eaaf' : '#ff6876' }}>
                        OPEN {activeTrade.side} ({activeTrade.quantity} Qty)
                      </span>
                      <span style={{ fontSize: '10px', background: '#051b2c', padding: '2px 5px', borderRadius: '3px', color: '#88a3b8' }}>
                        {activeTrade.status}
                      </span>
                    </div>
                    <span style={{ fontSize: '10px', color: '#88a3b8' }}>
                      Duration: {formatDuration(activeTrade.entry_timestamp)}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '11px', marginBottom: '10px' }}>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Entry Price: </span>
                      <strong>₹{formatPrice(activeTrade.entry_price)}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>{isHistorical ? 'Historical Close: ' : 'Current Price: '}</span>
                      <strong>{displayPrice}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Unrealized P&L: </span>
                      <strong style={{ color: liveUnrealizedPnl >= 0 ? '#00eaaf' : '#ff6876' }}>
                        {liveUnrealizedPnl >= 0 ? '+' : ''}₹{formatPrice(liveUnrealizedPnl)}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Trade ID: </span>
                      <span style={{ fontFamily: 'monospace', color: '#a0c0d8' }}>{activeTrade.trade_id}</span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleClosePaperTrade}
                    disabled={actionLoading}
                    style={{
                      width: '100%',
                      padding: '7px 0',
                      borderRadius: '4px',
                      border: '1px solid rgba(255, 79, 94, 0.5)',
                      background: 'linear-gradient(180deg, #ff4f5e 0%, #d92d3c 100%)',
                      color: '#ffffff',
                      fontWeight: 'bold',
                      fontSize: '11.5px',
                      cursor: 'pointer',
                    }}
                  >
                    {actionLoading ? 'CLOSING POSITION...' : 'CLOSE PAPER TRADE'}
                  </button>
                </div>
              ) : showConfirmModal ? (
                /* Case B: Confirmation Form */
                <div className="paper-confirm-box" style={{ background: 'rgba(7, 26, 45, 0.95)', border: '1px solid rgba(16, 132, 255, 0.5)', borderRadius: '6px', padding: '10px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#7cb5ec', marginBottom: '6px' }}>
                    CONFIRM SIMULATED ORDER
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px', fontSize: '11px', marginBottom: '8px' }}>
                    <div><span style={{ color: '#88a3b8' }}>Symbol:</span> <strong>{symbol}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Side:</span> <strong>{rawSignal === 'BUY' ? 'BUY (LONG)' : 'SELL (SHORT)'}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Timeframe:</span> <strong>{timeframe}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Entry:</span> <strong>₹{formatPrice(entryPrice)}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Stop Loss:</span> <strong style={{ color: '#ff6876' }}>₹{formatPrice(stopLoss)}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Target 1:</span> <strong style={{ color: '#00eaaf' }}>₹{formatPrice(target1)}</strong></div>
                    <div><span style={{ color: '#88a3b8' }}>Target 2:</span> <strong style={{ color: '#00eaaf' }}>₹{formatPrice(target2)}</strong></div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span style={{ color: '#88a3b8' }}>Quantity:</span>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={orderQuantity}
                        onChange={(e) => setOrderQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                        style={{ width: '50px', background: '#020b14', border: '1px solid #1a3a54', color: '#fff', padding: '2px 4px', borderRadius: '3px', fontSize: '11px' }}
                      />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={handleConfirmPaperTrade}
                      disabled={actionLoading}
                      style={{
                        flex: 1,
                        padding: '6px 0',
                        borderRadius: '4px',
                        border: '0',
                        background: 'linear-gradient(180deg, #00d9a3 0%, #00a87e 100%)',
                        color: '#021019',
                        fontWeight: 'bold',
                        fontSize: '11px',
                        cursor: 'pointer',
                      }}
                    >
                      {actionLoading ? 'SUBMITTING...' : 'CONFIRM PAPER TRADE'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowConfirmModal(false)}
                      disabled={actionLoading}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '4px',
                        border: '1px solid #23425d',
                        background: '#0a1d2f',
                        color: '#a0b4c5',
                        fontSize: '11px',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : rawSignal === 'BUY' || rawSignal === 'SELL' ? (
                /* Case C: Trigger Button Available */
                (isHistorical || symbol === 'NIFTY 50' || symbol === 'NIFTY' || symbol === '^NSEI') ? (
                  <div
                    className="paper-trading-disabled-banner"
                    style={{
                      padding: '8px 10px',
                      background: 'rgba(255, 179, 0, 0.1)',
                      border: '1px solid rgba(255, 179, 0, 0.3)',
                      borderRadius: '4px',
                      color: '#ffb300',
                      fontSize: '11px',
                      textAlign: 'center',
                      margin: '8px 0',
                    }}
                  >
                    <span style={{ fontWeight: 'bold' }}>⚡ PAPER TRADE UNAVAILABLE: </span>
                    Paper trading unavailable: historical market data only. Latest available data: 26 Mar 2024.
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowConfirmModal(true)}
                    style={{
                      width: '100%',
                      padding: '8px 0',
                      borderRadius: '4px',
                      border: '1px solid rgba(0, 217, 163, 0.4)',
                      background: rawSignal === 'BUY'
                        ? 'linear-gradient(180deg, rgba(0, 217, 163, 0.2) 0%, rgba(0, 168, 126, 0.3) 100%)'
                        : 'linear-gradient(180deg, rgba(255, 79, 94, 0.2) 0%, rgba(217, 45, 60, 0.3) 100%)',
                      color: rawSignal === 'BUY' ? '#00eaaf' : '#ff6876',
                      fontWeight: 'bold',
                      fontSize: '12px',
                      letterSpacing: '0.04em',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      transition: 'all 150ms ease',
                    }}
                  >
                    <span>⚡ PAPER TRADE ({rawSignal})</span>
                  </button>
                )
              ) : (
                /* Case D: NO_TRADE setup */
                <div
                  style={{
                    padding: '8px 10px',
                    background: 'rgba(4, 16, 27, 0.6)',
                    border: '1px dashed #1a3a54',
                    borderRadius: '4px',
                    fontSize: '10.5px',
                    color: '#658299',
                    textAlign: 'center',
                  }}
                >
                  <strong style={{ display: 'block', color: '#88a3b8', marginBottom: '2px' }}>
                    PAPER TRADING UNAVAILABLE
                  </strong>
                  <span>Strategy Signal is NO TRADE — trade execution requires an active BUY or SELL setup.</span>
                </div>
              )}
            </div>

            {/* 5. Historical Backtest Engine Bridge */}
            <div className="backtest-engine-section" style={{ marginTop: '16px', borderTop: '1px solid #1a3a54', paddingTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="detail-muted-title">HISTORICAL BACKTEST ENGINE</span>
                <span
                  className={`status-pill ${backtestStatus.toLowerCase()}`}
                  style={{
                    fontSize: '10px',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontWeight: 'bold',
                    textTransform: 'uppercase',
                    background:
                      backtestStatus === 'COMPLETED'
                        ? 'rgba(0, 234, 175, 0.15)'
                        : backtestStatus === 'RUNNING' || backtestStatus === 'QUEUED'
                          ? 'rgba(255, 170, 0, 0.15)'
                          : backtestStatus === 'FAILED'
                            ? 'rgba(255, 79, 94, 0.15)'
                            : '#0d2238',
                    color:
                      backtestStatus === 'COMPLETED'
                        ? '#00eaaf'
                        : backtestStatus === 'RUNNING' || backtestStatus === 'QUEUED'
                          ? '#ffaa00'
                          : backtestStatus === 'FAILED'
                            ? '#ff6876'
                            : '#88a3b8',
                  }}
                >
                  {backtestStatus}
                </span>
              </div>

              {/* Parameters Form */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '11px', marginBottom: '8px' }}>
                <div>
                  <label htmlFor="bt-start-date" style={{ color: '#88a3b8', display: 'block', marginBottom: '2px' }}>Start Date:</label>
                  <input
                    id="bt-start-date"
                    type="date"
                    value={backtestStartDate}
                    onChange={(e) => setBacktestStartDate(e.target.value)}
                    max={symbol === 'NIFTY 50' || symbol === 'NIFTY' || symbol === '^NSEI' ? '2024-03-26' : undefined}
                    disabled={backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'}
                    style={{ width: '100%', background: '#020b14', border: '1px solid #1a3a54', color: '#fff', padding: '3px 6px', borderRadius: '3px', fontSize: '11px' }}
                  />
                </div>
                <div>
                  <label htmlFor="bt-end-date" style={{ color: '#88a3b8', display: 'block', marginBottom: '2px' }}>End Date:</label>
                  <input
                    id="bt-end-date"
                    type="date"
                    value={backtestEndDate}
                    onChange={(e) => setBacktestEndDate(e.target.value)}
                    max={symbol === 'NIFTY 50' || symbol === 'NIFTY' || symbol === '^NSEI' ? '2024-03-26' : undefined}
                    disabled={backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'}
                    style={{ width: '100%', background: '#020b14', border: '1px solid #1a3a54', color: '#fff', padding: '3px 6px', borderRadius: '3px', fontSize: '11px' }}
                  />
                </div>
                <div>
                  <label htmlFor="bt-exec-model" style={{ color: '#88a3b8', display: 'block', marginBottom: '2px' }}>Execution Model:</label>
                  <select
                    id="bt-exec-model"
                    value={backtestExecutionModel}
                    onChange={(e) => setBacktestExecutionModel(e.target.value)}
                    disabled={backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'}
                    style={{ width: '100%', background: '#020b14', border: '1px solid #1a3a54', color: '#fff', padding: '3px 6px', borderRadius: '3px', fontSize: '11px' }}
                  >
                    <option value="next_open">next_open (Causal) [Realistic]</option>
                    <option value="same_close">same_close (Theoretical) [Lookahead Biased]</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="bt-capital" style={{ color: '#88a3b8', display: 'block', marginBottom: '2px' }}>Capital (₹):</label>
                  <input
                    id="bt-capital"
                    type="number"
                    value={backtestInitialCapital}
                    onChange={(e) => setBacktestInitialCapital(Number(e.target.value))}
                    disabled={backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'}
                    style={{ width: '100%', background: '#020b14', border: '1px solid #1a3a54', color: '#fff', padding: '3px 6px', borderRadius: '3px', fontSize: '11px' }}
                  />
                </div>
              </div>

              {/* Active Job Progress */}
              {(backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING') && (
                <div style={{ marginBottom: '8px', padding: '8px', background: 'rgba(255, 170, 0, 0.08)', borderRadius: '4px', border: '1px solid rgba(255, 170, 0, 0.25)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10.5px', marginBottom: '4px' }}>
                    <span style={{ color: '#ffaa00' }}>Job ID: <code>{backtestJobId}</code></span>
                    <span style={{ color: '#fff', fontWeight: 'bold' }}>{backtestProgress}%</span>
                  </div>
                  <div style={{ width: '100%', height: '4px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '2px', overflow: 'hidden', marginBottom: '6px' }}>
                    <div style={{ width: `${backtestProgress}%`, height: '100%', background: '#ffaa00', transition: 'width 300ms ease' }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '9.5px', color: '#88a3b8' }}>Cooperative cancellation checkpoint</span>
                    <button
                      type="button"
                      id="bt-cancel-btn"
                      onClick={handleCancelBacktest}
                      disabled={cancellingBacktest}
                      style={{
                        background: 'rgba(255, 79, 94, 0.15)',
                        border: '1px solid rgba(255, 79, 94, 0.4)',
                        color: '#ff6876',
                        borderRadius: '3px',
                        padding: '2px 8px',
                        fontSize: '10px',
                        cursor: cancellingBacktest ? 'not-allowed' : 'pointer',
                        fontWeight: 'bold',
                      }}
                    >
                      {cancellingBacktest ? 'CANCELLING...' : 'CANCEL BACKTEST'}
                    </button>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {backtestError && (
                <div style={{ padding: '6px 8px', marginBottom: '8px', background: 'rgba(255, 79, 94, 0.1)', border: '1px solid rgba(255, 79, 94, 0.3)', borderRadius: '4px', color: '#ff6876', fontSize: '11px' }}>
                  <strong>Error:</strong> {backtestError}
                </div>
              )}

              {/* Completed Results Grid */}
              {backtestResult && (
                <div className="backtest-results-box" style={{ marginBottom: '8px', padding: '8px', background: 'rgba(0, 234, 175, 0.05)', borderRadius: '4px', border: '1px solid rgba(0, 234, 175, 0.2)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#00eaaf', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>SIMULATION RESULTS ({backtestResult.symbol})</span>
                    <span style={{ color: '#88a3b8', fontSize: '10px' }}>{backtestResult.date_range?.total_candles} candles</span>
                  </div>
                  {backtestResult.execution_model === 'same_close' ? (
                    <div style={{ padding: '3px 6px', marginBottom: '6px', background: 'rgba(255, 79, 94, 0.15)', border: '1px solid rgba(255, 79, 94, 0.4)', borderRadius: '3px', color: '#ff6876', fontSize: '9.5px', fontWeight: 'bold' }}>
                      ⚠️ THEORETICAL EXECUTION (LOOKAHEAD BIASED / NON-CAUSAL)
                    </div>
                  ) : (
                    <div style={{ padding: '3px 6px', marginBottom: '6px', background: 'rgba(0, 234, 175, 0.1)', border: '1px solid rgba(0, 234, 175, 0.3)', borderRadius: '3px', color: '#00eaaf', fontSize: '9.5px', fontWeight: 'bold' }}>
                      ✅ CAUSAL REALISTIC EXECUTION (NEXT-OPEN BAR FILL)
                    </div>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '11px' }}>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Net Return: </span>
                      <strong style={{ color: backtestResult.metrics.total_return_pct >= 0 ? '#00eaaf' : '#ff6876' }}>
                        {backtestResult.metrics.total_return_pct >= 0 ? '+' : ''}{backtestResult.metrics.total_return_pct}%
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Total P&L: </span>
                      <strong style={{ color: backtestResult.metrics.total_pnl >= 0 ? '#00eaaf' : '#ff6876' }}>
                        ₹{formatPrice(backtestResult.metrics.total_pnl)}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Trades: </span>
                      <strong>{backtestResult.metrics.total_trades}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Win Rate: </span>
                      <strong>{backtestResult.metrics.win_rate_pct}%</strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Profit Factor: </span>
                      <strong>{backtestResult.metrics.profit_factor}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#88a3b8' }}>Max DD: </span>
                      <strong style={{ color: '#ff6876' }}>-{backtestResult.metrics.max_drawdown_pct}%</strong>
                    </div>
                  </div>

                  {/* Interactive Analytics & Tearsheet Trigger Actions */}
                  <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      id="bt-view-analytics-btn"
                      onClick={() => setShowAnalyticsModal(true)}
                      style={{
                        flex: 1,
                        padding: '6px 8px',
                        background: '#13283c',
                        border: '1px solid #1f4263',
                        borderRadius: '3px',
                        color: '#00eaaf',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                      }}
                    >
                      📊 INTERACTIVE ANALYTICS
                    </button>
                    <a
                      href={getBacktestTearsheetUrl(backtestResult.job_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      id="bt-view-tearsheet-btn"
                      style={{
                        flex: 1,
                        padding: '6px 8px',
                        background: '#0e1d2c',
                        border: '1px solid #1a354f',
                        borderRadius: '3px',
                        color: '#7cb5ec',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        textAlign: 'center',
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                      }}
                    >
                      📑 TEARSHEET
                    </a>
                  </div>
                </div>
              )}

              {/* Run Button */}
              <button
                type="button"
                onClick={handleTriggerBacktest}
                disabled={backtestSubmitting || backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'}
                style={{
                  width: '100%',
                  padding: '8px 0',
                  borderRadius: '4px',
                  border: '1px solid #1a3a54',
                  background:
                    backtestStatus === 'RUNNING' || backtestStatus === 'QUEUED'
                      ? '#13283c'
                      : 'linear-gradient(180deg, #123456 0%, #0a2036 100%)',
                  color: backtestStatus === 'RUNNING' || backtestStatus === 'QUEUED' ? '#88a3b8' : '#7cb5ec',
                  fontWeight: 'bold',
                  fontSize: '11.5px',
                  letterSpacing: '0.04em',
                  cursor: backtestStatus === 'RUNNING' || backtestStatus === 'QUEUED' ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                }}
              >
                {backtestStatus === 'QUEUED' || backtestStatus === 'RUNNING'
                  ? `SIMULATING BACKTEST (${backtestProgress}%)...`
                  : 'RUN HISTORICAL BACKTEST'}
              </button>
            </div>

            {/* 6. View Full Analysis Action */}
            {onNavigateFullAnalysis && (
              <button
                type="button"
                className="full-analysis-btn"
                onClick={onNavigateFullAnalysis}
              >
                <span>View Full Analysis</span>
                <PanelIcon type="arrow-right" />
              </button>
            )}
          </>
        )}
      </div>

      {/* Interactive Backtest Analytics & Equity Curves Modal */}
      {showAnalyticsModal && backtestResult && (
        <BacktestAnalyticsModal
          isOpen={showAnalyticsModal}
          onClose={() => setShowAnalyticsModal(false)}
          result={backtestResult}
        />
      )}
    </div>
  )
}
