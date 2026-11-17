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
  fetchPaperOrders,
  submitPaperOrder,
  cancelPaperOrder,
  fetchPaperLedger,
  fetchPaperMarketDataHealth,
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
  const [orders, setOrders] = useState([])
  const [ledgerReport, setLedgerReport] = useState(null)
  const [marketDataHealth, setMarketDataHealth] = useState(null)

  // Filters for Trade History
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterSide, setFilterSide] = useState('')
  const [filterTimeframe, setFilterTimeframe] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  // Simulated Order Form State
  const [orderSymbol, setOrderSymbol] = useState('RELIANCE')
  const [orderSide, setOrderSide] = useState('BUY')
  const [orderType, setOrderType] = useState('MARKET')
  const [orderQty, setOrderQty] = useState(10)
  const [orderPrice, setOrderPrice] = useState(2500)
  const [orderStopLoss, setOrderStopLoss] = useState(2475)
  const [submittingOrder, setSubmittingOrder] = useState(false)
  const [cancellingOrderId, setCancellingOrderId] = useState(null)
  const [showLedgerEntries, setShowLedgerEntries] = useState(false)

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
        ordersResult,
        ledgerResult,
        healthResult,
      ] = await Promise.all([
        fetchPaperTradingStatus().catch(() => null),
        fetchPaperTradingReport().catch(() => null),
        fetchPaperTradingTrades({
          symbol: filterSymbol || undefined,
          side: filterSide || undefined,
          timeframe: filterTimeframe || undefined,
          status: filterStatus || undefined,
        }).catch(() => []),
        fetchOpenPaperTrades().catch(() => []),
        fetchPaperTradingSummary().catch(() => null),
        fetchPaperOrders().catch(() => []),
        fetchPaperLedger().catch(() => null),
        fetchPaperMarketDataHealth().catch(() => null),
      ])

      setStatus(statusResult)
      setReport(reportResult)
      setTrades(Array.isArray(tradesResult) ? tradesResult : [])
      setOpenTrades(Array.isArray(openTradesResult) ? openTradesResult : [])
      setSummary(summaryResult)
      setOrders(Array.isArray(ordersResult) ? ordersResult : [])
      setLedgerReport(ledgerResult)
      setMarketDataHealth(healthResult)
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

  async function handleOrderSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    setSubmittingOrder(true)
    try {
      await submitPaperOrder({
        symbol: orderSymbol,
        side: orderSide,
        order_type: orderType,
        quantity: parseInt(orderQty, 10),
        price: parseFloat(orderPrice),
        current_market_price: parseFloat(orderPrice),
        stop_price: orderStopLoss ? parseFloat(orderStopLoss) : undefined,
      })
      toast.success(`Simulated ${orderSide} order for ${orderSymbol} placed.`, { title: 'Order Submitted' })
      await loadPaperTradingData()
    } catch (err) {
      toast.error(err.message || 'Failed to submit simulated order.', { title: 'Order Rejected' })
    } finally {
      setSubmittingOrder(false)
    }
  }

  async function handleOrderCancel(orderId) {
    setCancellingOrderId(orderId)
    try {
      await cancelPaperOrder(orderId)
      toast.success(`Order ${orderId} cancelled.`, { title: 'Order Cancelled' })
      await loadPaperTradingData()
    } catch (err) {
      toast.error(err.message || 'Failed to cancel order.', { title: 'Cancel Failed' })
    } finally {
      setCancellingOrderId(null)
    }
  }

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
            Simulated paper trading powered by SignalForge strategy signals with zero look-ahead bias and deterministic execution.
          </p>
        </div>

        <div className="paper-page-actions">
          <div className="paper-mode-badge-large">
            <span className="paper-mode-dot" />
            <span>SIMULATION ONLY • NO REAL MONEY</span>
          </div>
        </div>
      </header>

      {/* Phase 28: Prominent Simulation Warning Banner & Data Health */}
      <div
        className="paper-simulation-banner"
        style={{
          padding: '12px 18px',
          background: 'rgba(255, 68, 68, 0.12)',
          border: '1px solid rgba(255, 68, 68, 0.35)',
          borderRadius: '8px',
          color: '#ff7878',
          fontSize: '13px',
          fontWeight: '700',
          letterSpacing: '0.5px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '18px' }}>🛡️</span>
          <span>PAPER / SIMULATION ONLY — NO BROKER CONNECTED • ZERO REAL CAPITAL RISK</span>
        </div>
        {marketDataHealth && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', background: 'rgba(0,0,0,0.3)', padding: '4px 10px', borderRadius: '4px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: marketDataHealth.data_quality_state === 'CONNECTED' ? '#00eaaf' : '#ffb300',
                display: 'inline-block',
              }}
            />
            <span>Feed: {marketDataHealth.data_quality_state}</span>
          </div>
        )}
      </div>

      <div
        className="paper-trading-historical-notice"
        style={{
          padding: '10px 14px',
          background: 'rgba(255, 179, 0, 0.08)',
          border: '1px solid rgba(255, 179, 0, 0.25)',
          borderRadius: '6px',
          color: '#ffb300',
          fontSize: '12px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <span>⚠️</span>
        <span>
          <strong>Market Data Status:</strong> Paper trading unavailable: historical market data only. Latest available data: 26 Mar 2024. New paper orders for NIFTY 50 cannot be opened against historical datasets.
        </span>
      </div>

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
              subValue="Unclosed ledger positions"
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
              subtitle="Simulated positions with status OPEN in local paper ledger."
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

          {/* Phase 28: Portfolio Risk & Margin Discipline Panel */}
          {ledgerReport && (
            <section className="paper-session-panel" style={{ marginTop: '20px' }}>
              <SectionHeader
                title="Capital Accounting & Portfolio Risk Discipline"
                subtitle="Double-entry ledger reconciliation, margin allocations, and pre-trade risk safeguards."
                right={
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: '700',
                      background: ledgerReport.is_balanced ? 'rgba(0, 234, 175, 0.15)' : 'rgba(255, 100, 114, 0.15)',
                      color: ledgerReport.is_balanced ? '#00eaaf' : '#ff6472',
                      border: `1px solid ${ledgerReport.is_balanced ? 'rgba(0, 234, 175, 0.3)' : 'rgba(255, 100, 114, 0.3)'}`,
                    }}
                  >
                    {ledgerReport.is_balanced ? '✓ LEDGER BALANCED' : '⚠️ RECONCILIATION DISCREPANCY'}
                  </span>
                }
              />

              <div className="paper-stats-grid" style={{ marginTop: '14px' }}>
                <StatCard
                  label="Total Account Equity"
                  value={formatCurrency(ledgerReport.total_equity)}
                  subValue={`Cash ₹${(ledgerReport.cash_balance || 0).toFixed(0)} + Unrealized ₹${(ledgerReport.unrealized_pnl || 0).toFixed(0)}`}
                  className={getPnlClass(ledgerReport.total_equity - ledgerReport.initial_deposit)}
                />
                <StatCard
                  label="Available Margin"
                  value={formatCurrency(ledgerReport.available_margin)}
                  subValue="Deployable capital for new trades"
                />
                <StatCard
                  label="Allocated Margin"
                  value={formatCurrency(ledgerReport.allocated_margin)}
                  subValue="Active margin locked in positions"
                />
                <StatCard
                  label="Reserved Capital (15%)"
                  value={formatCurrency(ledgerReport.reserved_capital)}
                  subValue="Capital preservation buffer"
                />
              </div>

              {/* Safeguard Status Bar */}
              <div
                style={{
                  marginTop: '14px',
                  padding: '10px 14px',
                  background: 'rgba(12, 31, 45, 0.6)',
                  borderRadius: '6px',
                  border: '1px solid #142a3a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', color: '#88a3b8' }}>
                  <span>Max Per-Trade Risk: <strong style={{ color: '#fff' }}>1.0%</strong></span>
                  <span>Max Symbol Allocation: <strong style={{ color: '#fff' }}>35.0%</strong></span>
                  <span>Max Aggregate Risk: <strong style={{ color: '#fff' }}>3.0%</strong></span>
                  <span>Square-Off Cutoff: <strong style={{ color: '#fff' }}>15:15 IST</strong></span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowLedgerEntries(!showLedgerEntries)}
                  style={{
                    background: 'transparent',
                    border: '1px solid #23425d',
                    borderRadius: '4px',
                    color: '#7cb5ec',
                    fontSize: '11px',
                    padding: '4px 10px',
                    cursor: 'pointer',
                  }}
                >
                  {showLedgerEntries ? 'Hide Audit Journal ▲' : `View Audit Journal (${ledgerReport.entries?.length || 0} entries) ▼`}
                </button>
              </div>

              {/* Expandable Journal Table */}
              {showLedgerEntries && (
                <div className="paper-table-scroll" style={{ marginTop: '12px' }}>
                  <div className="paper-trades-table">
                    <div className="paper-table-head">
                      <span>Entry ID</span>
                      <span>Timestamp</span>
                      <span>Type</span>
                      <span className="text-right">Amount</span>
                      <span className="text-right">Balance After</span>
                      <span>Trade / Order ID</span>
                      <span>Description</span>
                    </div>
                    {(ledgerReport.entries || []).map((e) => (
                      <div className="paper-trade-row" key={e.entry_id}>
                        <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#88a3b8' }}>{e.entry_id}</span>
                        <span style={{ fontSize: '11px' }}>{formatTimestamp(e.timestamp)}</span>
                        <span style={{ fontWeight: '600', color: e.entry_type.includes('RELEASE') || e.entry_type.includes('DEPOSIT') ? '#00eaaf' : '#ffb300' }}>{e.entry_type}</span>
                        <span className="text-right tabular-num">{formatCurrency(e.amount)}</span>
                        <span className="text-right tabular-num">{formatCurrency(e.balance_after)}</span>
                        <span style={{ fontFamily: 'monospace', fontSize: '10px' }}>{e.trade_id || e.order_id || '—'}</span>
                        <span style={{ color: '#88a3b8', fontSize: '11px' }}>{e.description}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Phase 28: Simulated Orders & Order Book */}
          <section className="paper-session-panel" style={{ marginTop: '20px' }}>
            <SectionHeader
              title="Simulated Order Book & Execution"
              subtitle="Causal fill simulation on authentic quotes with deterministic slippage (1 bps) and half-spread (0.5 bps)."
              right={
                <span className="paper-trade-count">
                  {orders.length} orders
                </span>
              }
            />

            {/* Quick Simulated Order Form */}
            <form onSubmit={handleOrderSubmit} style={{ display: 'flex', gap: '10px', padding: '12px 0', borderBottom: '1px solid #142a3a', flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Symbol (e.g. RELIANCE)"
                value={orderSymbol}
                onChange={(e) => setOrderSymbol(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px', width: '110px' }}
                required
              />
              <select
                value={orderSide}
                onChange={(e) => setOrderSide(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px' }}
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
              <select
                value={orderType}
                onChange={(e) => setOrderType(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px' }}
              >
                <option value="MARKET">MARKET</option>
                <option value="LIMIT">LIMIT</option>
                <option value="STOP_LOSS">STOP_LOSS</option>
              </select>
              <input
                type="number"
                placeholder="Qty"
                min="1"
                value={orderQty}
                onChange={(e) => setOrderQty(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px', width: '65px' }}
                required
              />
              <input
                type="number"
                step="0.05"
                placeholder="Price"
                value={orderPrice}
                onChange={(e) => setOrderPrice(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px', width: '85px' }}
                required
              />
              <input
                type="number"
                step="0.05"
                placeholder="Stop Loss"
                value={orderStopLoss}
                onChange={(e) => setOrderStopLoss(e.target.value)}
                style={{ height: '32px', padding: '0 8px', background: '#051525', border: '1px solid #1a374b', borderRadius: '4px', color: '#fff', fontSize: '11px', width: '85px' }}
              />
              <button
                type="submit"
                disabled={submittingOrder}
                style={{
                  height: '32px',
                  padding: '0 14px',
                  background: orderSide === 'BUY' ? '#00d9a3' : '#ff6472',
                  border: '0',
                  borderRadius: '4px',
                  color: '#051525',
                  fontSize: '11px',
                  fontWeight: '700',
                  cursor: 'pointer',
                }}
              >
                {submittingOrder ? 'Submitting…' : `Submit Simulated ${orderSide}`}
              </button>
            </form>

            <div className="paper-table-scroll">
              <div className="paper-trades-table">
                <div className="paper-table-head">
                  <span>Order ID</span>
                  <span>Symbol</span>
                  <span>Side</span>
                  <span>Type</span>
                  <span className="text-right">Qty</span>
                  <span className="text-right">Req Price</span>
                  <span className="text-right">Fill Price</span>
                  <span className="text-right">Slippage</span>
                  <span className="text-right">Costs</span>
                  <span>Status</span>
                  <span className="text-right">Action</span>
                </div>

                {orders.length === 0 ? (
                  <EmptyState
                    title="No Simulated Orders"
                    description="Submit a simulated order above or trigger a signal from the Strategy Signal Panel."
                    compact
                  />
                ) : (
                  orders.map((ord) => (
                    <div className="paper-trade-row" key={ord.order_id}>
                      <span style={{ fontFamily: 'monospace', color: '#88a3b8', fontSize: '10px' }}>{ord.order_id}</span>
                      <strong>{ord.symbol}</strong>
                      <span className={`paper-position ${ord.side.toLowerCase()}`}>{ord.side}</span>
                      <span>{ord.order_type}</span>
                      <span className="text-right tabular-num">{ord.quantity}</span>
                      <span className="text-right tabular-num">{formatCurrency(ord.price)}</span>
                      <span className="text-right tabular-num">{ord.fill_price ? formatCurrency(ord.fill_price) : '—'}</span>
                      <span className="text-right tabular-num" style={{ color: '#88a3b8', fontSize: '11px' }}>
                        {ord.slippage_bps ? `${ord.slippage_bps.toFixed(1)} bps` : '—'}
                      </span>
                      <span className="text-right tabular-num">{formatCurrency(ord.transaction_cost)}</span>
                      <span>
                        <span
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: ord.status === 'FILLED' ? 'rgba(0, 234, 175, 0.15)' : ord.status === 'REJECTED' || ord.status === 'CANCELLED' ? 'rgba(255, 100, 114, 0.15)' : 'rgba(76, 168, 255, 0.15)',
                            color: ord.status === 'FILLED' ? '#00eaaf' : ord.status === 'REJECTED' || ord.status === 'CANCELLED' ? '#ff6472' : '#7cb5ec',
                          }}
                        >
                          {ord.status}
                        </span>
                      </span>
                      <span className="text-right">
                        {ord.status === 'SUBMITTED' || ord.status === 'PENDING_EXECUTION' ? (
                          <button
                            type="button"
                            onClick={() => handleOrderCancel(ord.order_id)}
                            disabled={cancellingOrderId === ord.order_id}
                            style={{
                              padding: '3px 8px',
                              background: '#3d1d24',
                              border: '1px solid #7a2b36',
                              borderRadius: '3px',
                              color: '#ff6472',
                              fontSize: '10px',
                              cursor: 'pointer',
                            }}
                          >
                            {cancellingOrderId === ord.order_id ? '…' : 'Cancel'}
                          </button>
                        ) : (
                          <span style={{ color: '#587286', fontSize: '10px' }}>—</span>
                        )}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
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