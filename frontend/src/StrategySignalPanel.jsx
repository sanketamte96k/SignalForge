import React from 'react'
import { LoadingState, ErrorState, EmptyState } from './StateViews'

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

  return (
    <div className="signal-panel panel" aria-label="Strategy Signal Panel">
      <div className="panel-header signal-panel-header">
        <div className="signal-header-left">
          <h2>{signalData?.symbol || 'NIFTY 50'} • Strategy Signal</h2>
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
                <strong className="instrument-title">
                  {signalData.symbol || 'NIFTY 50 Index'}
                </strong>
              </div>
              <div className="signal-metric-row">
                <span className="detail-muted">Current Price</span>
                <strong className="numeric-val tabular-num">{displayPrice}</strong>
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
                  className={`confirmation-status-pill ${
                    confirmationStatus === 'Confirmed'
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
                {/* EMA Confirmation */}
                <div
                  className={`factor-item ${
                    emaConfirmed ? 'factor-confirmed' : 'factor-neutral'
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

                {/* RSI + Momentum Confirmation */}
                <div
                  className={`factor-item ${
                    rsiConfirmed ? 'factor-confirmed' : 'factor-neutral'
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

                {/* Volume Confirmation */}
                <div
                  className={`factor-item ${
                    volumeConfirmed ? 'factor-confirmed' : 'factor-neutral'
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

                {/* Multi-Timeframe Alignment */}
                <div
                  className={`factor-item ${
                    mtfConfirmed ? 'factor-confirmed' : 'factor-neutral'
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

            {/* 5. View Full Analysis Action */}
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
    </div>
  )
}
