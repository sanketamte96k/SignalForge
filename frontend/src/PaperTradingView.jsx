import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPaperTradingReport,
  fetchPaperTradingStatus,
  fetchPaperTradingTrades,
  fetchOpenPaperTrades,
  fetchPaperTradingSummary,
  closePaperTrade,
  resetPaperTrading,
  startPaperTrading,
} from './api'
import './PaperTradingView.css'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import { useToast } from './useToast'
import { sanitizeErrorMessage } from './stateUtils'

function formatCurrency(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—'
  }

  return `₹${value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
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

function formatPercent(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—'
  }

  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '—'
  }

  const date = new Date(timestamp)

  if (Number.isNaN(date.getTime())) {
    return String(timestamp)
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(date)
}

function getPnlClass(value) {
  if (typeof value !== 'number') {
    return ''
  }

  if (value > 0) {
    return 'paper-positive'
  }

  if (value < 0) {
    return 'paper-negative'
  }

  return 'paper-neutral'
}

function getPositionLabel(position) {
  if (position === 'LONG' || position === 'BUY') {
    return 'LONG'
  }

  if (position === 'SHORT' || position === 'SELL') {
    return 'SHORT'
  }

  return position || '—'
}

function StatCard({
  label,
  value,
  subValue,
  className = '',
}) {
  return (
    <div className={`paper-stat-card ${className}`}>
      <div className="paper-stat-icon" aria-hidden="true">
        <span />
      </div>

      <div className="paper-stat-content">
        <span className="paper-stat-label">{label}</span>

        <strong className="paper-stat-value tabular-num">
          {value}
        </strong>

        {subValue && (
          <span className="paper-stat-sub tabular-num">
            {subValue}
          </span>
        )}
      </div>
    </div>
  )
}

function SectionHeader({
  title,
  subtitle,
  right,
}) {
  return (
    <div className="paper-section-header">
      <div>
        <h2>{title}</h2>

        {subtitle && (
          <p>{subtitle}</p>
        )}
      </div>

      {right && (
        <div className="paper-section-header-right">
          {right}
        </div>
      )}
    </div>
  )
}

function PaperTradingView() {
  let toast
  try {
    toast = useToast()
  } catch {
    toast = {
      success: () => {},
      error: () => {},
      warning: () => {},
      info: () => {},
    }
  }
  const [status, setStatus] = useState(null)
  const [report, setReport] = useState(null)
  const [trades, setTrades] = useState([])
  const [openTrades, setOpenTrades] = useState([])
  const [summary, setSummary] = useState(null)

  // Filters for Trade History
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterSide, setFilterSide] = useState('')
  const [filterTimeframe, setFilterTimeframe] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [closingTradeId, setClosingTradeId] = useState(null)
  const [error, setError] = useState(null)

  const loadPaperTradingData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [
        statusResult,
        reportResult,
        tradesResult,
        openTradesResult,
        summaryResult,
      ] = await Promise.all([
        fetchPaperTradingStatus(),
        fetchPaperTradingReport(),
        fetchPaperTradingTrades({
          symbol: filterSymbol || undefined,
          side: filterSide || undefined,
          timeframe: filterTimeframe || undefined,
          status: filterStatus || undefined,
        }),
        fetchOpenPaperTrades(),
        fetchPaperTradingSummary(),
      ])

      setStatus(statusResult)
      setReport(reportResult)
      setTrades(Array.isArray(tradesResult) ? tradesResult : [])
      setOpenTrades(Array.isArray(openTradesResult) ? openTradesResult : [])
      setSummary(summaryResult)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load Paper Trading data.',
      )
    } finally {
      setLoading(false)
    }
  }, [filterSymbol, filterSide, filterTimeframe, filterStatus])

  useEffect(() => {
    loadPaperTradingData()
  }, [loadPaperTradingData])

  async function handleClosePosition(tradeId, currentPrice) {
    setClosingTradeId(tradeId)
    try {
      await closePaperTrade(tradeId, {
        exit_price: currentPrice,
        reason: 'MANUAL_CLOSE',
      })
      toast.success(`Position ${tradeId} closed successfully.`, { title: 'Position Closed' })
      await loadPaperTradingData()
    } catch (err) {
      toast.error(err.message || 'Failed to close position.', { title: 'Close Failed' })
    } finally {
      setClosingTradeId(null)
    }
  }

  async function handleStartReplay() {
    if (starting || resetting) {
      return
    }

    setStarting(true)
    setError(null)

    try {
      await startPaperTrading()
      await loadPaperTradingData()
      toast.success('Paper Trading replay completed.', { title: 'Replay Active' })
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Paper Trading replay failed.')
      setError(msg)
      toast.error(msg, { title: 'Session Failed' })
    } finally {
      setStarting(false)
    }
  }

  async function handleReset() {
    if (starting || resetting) {
      return
    }

    setResetting(true)
    setError(null)

    try {
      await resetPaperTrading()
      await loadPaperTradingData()
      toast.success('Paper Trading session and positions reset.', { title: 'Session Reset' })
    } catch (requestError) {
      const msg = sanitizeErrorMessage(requestError, 'Unable to reset Paper Trading.')
      setError(msg)
      toast.error(msg, { title: 'Reset Failed' })
    } finally {
      setResetting(false)
    }
  }

  const displaySummary = summary || {
    total_trades: 0,
    open_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate: 0,
    gross_pnl: 0,
    average_trade: 0,
    largest_win: 0,
    largest_loss: 0,
  }

  const isBusy = starting || resetting

  return (
    <div className="paper-trading-view">
      <header className="paper-page-header">
        <div>
          <span className="paper-page-kicker">SIMULATED EXECUTION</span>
          <h1>Paper Trading Engine</h1>
          <p>
            Real-time simulated paper trading powered by SignalForge strategy signals with zero look-ahead bias and deterministic execution.
          </p>
        </div>

        <div className="paper-page-actions">
          <div className="paper-mode-badge-large">
            <span className="paper-mode-dot" />
            <span>SIMULATION ONLY • NO REAL MONEY</span>
          </div>
        </div>
      </header>

      {loading && !status && !summary ? (
        <LoadingState
          title="Loading Paper Trading State..."
          description="Connecting to deterministic execution engine..."
        />
      ) : error && !status && !summary ? (
        <ErrorState
          title="Paper Trading Offline"
          message={error}
          onRetry={loadPaperTradingData}
          retryLabel="Retry Connection"
        />
      ) : (
        <>
          {/* 1. Performance Summary (Phase 17J) */}
          <section className="paper-stats-grid">
            <StatCard
              label="Gross P&L"
              value={formatCurrency(displaySummary.gross_pnl)}
              subValue="Realized gross trading profit"
              className={`pnl ${getPnlClass(displaySummary.gross_pnl)}`}
            />

            <StatCard
              label="Win Rate"
              value={formatPercent(displaySummary.win_rate)}
              subValue={`${displaySummary.winning_trades} wins · ${displaySummary.losing_trades} losses`}
            />

            <StatCard
              label="Total Trades"
              value={formatNumber(displaySummary.total_trades, 0)}
              subValue={`${displaySummary.open_trades} active open`}
            />

            <StatCard
              label="Average Trade"
              value={formatCurrency(displaySummary.average_trade)}
              subValue="Gross P&L per trade"
              className={getPnlClass(displaySummary.average_trade)}
            />
          </section>

          <section className="paper-secondary-stats">
            <StatCard
              label="Open Trades"
              value={formatNumber(displaySummary.open_trades, 0)}
              subValue="Active in current market"
            />

            <StatCard
              label="Best Trade"
              value={formatCurrency(displaySummary.largest_win)}
              subValue="Largest winning trade"
              className="paper-positive"
            />

            <StatCard
              label="Worst Trade"
              value={formatCurrency(displaySummary.largest_loss)}
              subValue="Largest drawdown trade"
              className="paper-negative"
            />

            <StatCard
              label="Active Mode"
              value="GROSS P&L"
              subValue="Simulated zero-cost execution"
            />
          </section>

          {/* 2. Open Positions (Phase 17J) */}
          <section className="paper-session-panel" style={{ marginTop: '20px' }}>
            <SectionHeader
              title="Active Open Positions"
              subtitle="Positions currently active and monitoring Stop Loss / Targets."
              right={
                <span className="paper-trade-count" style={{ background: openTrades.length > 0 ? 'rgba(0, 217, 163, 0.2)' : undefined, color: openTrades.length > 0 ? '#00eaaf' : undefined }}>
                  {openTrades.length} open
                </span>
              }
            />

            {openTrades.length === 0 ? (
              <EmptyState
                title="No Active Positions"
                description="Open a paper trade from the Strategy Signal Panel when an active BUY or SELL signal triggers."
                compact
              />
            ) : (
              <div className="paper-table-scroll">
                <div className="paper-trades-table">
                  <div className="paper-table-head">
                    <span>Trade ID</span>
                    <span>Symbol</span>
                    <span>Side</span>
                    <span>Timeframe</span>
                    <span className="text-right">Entry Price</span>
                    <span className="text-right">Stop Loss</span>
                    <span className="text-right">Target 1</span>
                    <span className="text-right">Target 2</span>
                    <span className="text-right">Qty</span>
                    <span className="text-right">Unrealized P&L</span>
                    <span>Status</span>
                    <span className="text-right">Action</span>
                  </div>

                  {openTrades.map((ot) => (
                    <div className="paper-trade-row" key={ot.trade_id}>
                      <span style={{ fontFamily: 'monospace', color: '#88a3b8' }}>{ot.trade_id}</span>
                      <strong>{ot.symbol}</strong>
                      <span className={`paper-position ${ot.side.toLowerCase()}`}>
                        {ot.side}
                      </span>
                      <span>{ot.timeframe}</span>
                      <span className="text-right tabular-num">{formatCurrency(ot.entry_price)}</span>
                      <span className="text-right tabular-num" style={{ color: '#ff6876' }}>{formatCurrency(ot.stop_loss)}</span>
                      <span className="text-right tabular-num" style={{ color: '#00eaaf' }}>{formatCurrency(ot.target_1)}</span>
                      <span className="text-right tabular-num" style={{ color: '#00eaaf' }}>{formatCurrency(ot.target_2)}</span>
                      <span className="text-right tabular-num">{ot.quantity}</span>
                      <strong className={`text-right tabular-num ${getPnlClass(ot.unrealized_pnl)}`}>
                        {formatCurrency(ot.unrealized_pnl)}
                      </strong>
                      <span>
                        <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: '#0a2338', color: '#00eaaf' }}>
                          {ot.status}
                        </span>
                      </span>
                      <span className="text-right">
                        <button
                          type="button"
                          onClick={() => handleClosePosition(ot.trade_id, ot.entry_price)}
                          disabled={closingTradeId === ot.trade_id}
                          style={{
                            padding: '4px 10px',
                            background: '#d92d3c',
                            border: '0',
                            borderRadius: '3px',
                            color: '#fff',
                            fontSize: '11px',
                            fontWeight: 'bold',
                            cursor: 'pointer',
                          }}
                        >
                          {closingTradeId === ot.trade_id ? 'Closing...' : 'Close'}
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* 3. Trade History & Filters (Phase 17J) */}
          <section className="paper-trades-panel" style={{ marginTop: '20px' }}>
            <SectionHeader
              title="Trade History"
              subtitle="All executed and completed paper trades with audit trail."
              right={
                <span className="paper-trade-count">
                  {trades.length} trades
                </span>
              }
            />

            {/* Filter Controls Bar */}
            <div style={{ display: 'flex', gap: '10px', padding: '10px 0', borderBottom: '1px solid #142a3a', flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Filter Symbol..."
                value={filterSymbol}
                onChange={(e) => setFilterSymbol(e.target.value)}
                style={{ height: '30px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px', width: '130px' }}
              />

              <select
                value={filterSide}
                onChange={(e) => setFilterSide(e.target.value)}
                style={{ height: '30px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px' }}
              >
                <option value="">All Sides</option>
                <option value="LONG">LONG</option>
                <option value="SHORT">SHORT</option>
              </select>

              <select
                value={filterTimeframe}
                onChange={(e) => setFilterTimeframe(e.target.value)}
                style={{ height: '30px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px' }}
              >
                <option value="">All Timeframes</option>
                <option value="5m">5m</option>
                <option value="10m">10m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
              </select>

              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                style={{ height: '30px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px' }}
              >
                <option value="">All Statuses</option>
                <option value="OPEN">OPEN</option>
                <option value="TARGET_1_HIT">TARGET_1_HIT</option>
                <option value="TARGET_2_HIT">TARGET_2_HIT</option>
                <option value="STOPPED_OUT">STOPPED_OUT</option>
                <option value="CLOSED">CLOSED</option>
              </select>

              {(filterSymbol || filterSide || filterTimeframe || filterStatus) && (
                <button
                  type="button"
                  onClick={() => {
                    setFilterSymbol('')
                    setFilterSide('')
                    setFilterTimeframe('')
                    setFilterStatus('')
                  }}
                  style={{ height: '30px', padding: '0 10px', background: '#0a1e30', border: '1px solid #23425d', borderRadius: '4px', color: '#88a3b8', fontSize: '11px', cursor: 'pointer' }}
                >
                  Clear Filters
                </button>
              )}
            </div>

            <div className="paper-table-scroll">
              <div className="paper-trades-table">
                <div className="paper-table-head">
                  <span>#</span>
                  <span>Trade ID</span>
                  <span>Symbol</span>
                  <span>Side</span>
                  <span>Timeframe</span>
                  <span>Entry Time</span>
                  <span>Exit Time</span>
                  <span className="text-right">Entry</span>
                  <span className="text-right">Exit</span>
                  <span className="text-right">Qty</span>
                  <span className="text-right">Gross P&L</span>
                  <span>Status</span>
                  <span>Reason</span>
                </div>

                {trades.length === 0 ? (
                  <EmptyState
                    title="No Trades Found"
                    description="No trades match the current criteria. Start a paper trade from the Strategy Signal Panel or run historical replay."
                    compact
                  />
                ) : (
                  trades.map((trade, index) => {
                    const side = getPositionLabel(trade.side || trade.position)
                    const pnl = typeof trade.realized_pnl === 'number' ? trade.realized_pnl : (trade.gross_pnl || 0)

                    return (
                      <div className="paper-trade-row" key={trade.trade_id || index}>
                        <span className="paper-trade-number">{index + 1}</span>
                        <span style={{ fontFamily: 'monospace', color: '#88a3b8', fontSize: '10px' }}>
                          {trade.trade_id || `tr_${index+1}`}
                        </span>
                        <strong>{trade.symbol || 'NIFTY 50'}</strong>
                        <span className={`paper-position ${side.toLowerCase()}`}>
                          {side}
                        </span>
                        <span>{trade.timeframe || '15m'}</span>
                        <span className="tabular-num">
                          {formatTimestamp(trade.entry_timestamp || trade.entry_time)}
                        </span>
                        <span className="tabular-num">
                          {formatTimestamp(trade.exit_timestamp || trade.exit_time)}
                        </span>
                        <span className="text-right tabular-num">
                          {formatCurrency(trade.entry_price)}
                        </span>
                        <span className="text-right tabular-num">
                          {formatCurrency(trade.exit_price)}
                        </span>
                        <span className="text-right tabular-num">
                          {trade.quantity}
                        </span>
                        <strong className={`text-right tabular-num ${getPnlClass(pnl)}`}>
                          {formatCurrency(pnl)}
                        </strong>
                        <span>
                          <span style={{ fontSize: '9.5px', padding: '2px 5px', borderRadius: '3px', background: '#0a1d2f', color: trade.status === 'STOPPED_OUT' ? '#ff6876' : trade.status?.includes('TARGET') ? '#00eaaf' : '#7cb5ec' }}>
                            {trade.status || 'CLOSED'}
                          </span>
                        </span>
                        <span className="paper-trade-reason" title={trade.exit_reason || trade.reason || ''}>
                          {trade.exit_reason || trade.reason || '—'}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </section>

          {/* 4. Session Controls & Replay Engine */}
          <section className="paper-session-panel" style={{ marginTop: '20px' }}>
            <SectionHeader
              title="Session Reset & Historical Simulation"
              subtitle="Reset all paper trading state or run historical backfill replay."
              right={
                <div className="paper-control-actions">
                  <button
                    type="button"
                    className="paper-start-button"
                    onClick={handleStartReplay}
                    disabled={isBusy}
                  >
                    <span className="paper-button-icon">
                      {starting ? '…' : '▶'}
                    </span>
                    <span>{starting ? 'Running Replay…' : 'Run Historical Replay'}</span>
                  </button>

                  <button
                    type="button"
                    className="paper-reset-button"
                    onClick={handleReset}
                    disabled={isBusy}
                  >
                    <span>↻</span>
                    <span>{resetting ? 'Resetting…' : 'Reset Everything'}</span>
                  </button>
                </div>
              }
            />
          </section>

          <section className="paper-disclosure-panel">
            <div className="paper-disclosure-icon">i</div>
            <div>
              <strong>Simulated Paper Trading Only</strong>
              <p>
                SignalForge paper trading is completely simulated for forward validation and algorithmic performance evaluation. It does not place broker orders or risk real capital.
              </p>
            </div>
            <div className="paper-disclosure-source">
              <span>Engine</span>
              <strong>Causal Strategy Engine (5m, 10m, 15m, 30m)</strong>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default PaperTradingView