import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPaperTradingReport,
  fetchPaperTradingStatus,
  fetchPaperTradingTrades,
  resetPaperTrading,
  startPaperTrading,
} from './api'
import './PaperTradingView.css'
import { LoadingState, ErrorState, EmptyState } from './StateViews'

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
  if (position === 'LONG') {
    return 'LONG'
  }

  if (position === 'SHORT') {
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
  const [status, setStatus] = useState(null)
  const [report, setReport] = useState(null)
  const [trades, setTrades] = useState([])

  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState(null)

  const loadPaperTradingData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [
        statusResult,
        reportResult,
        tradesResult,
      ] = await Promise.all([
        fetchPaperTradingStatus(),
        fetchPaperTradingReport(),
        fetchPaperTradingTrades(),
      ])

      setStatus(statusResult)
      setReport(reportResult)

      setTrades(
        Array.isArray(tradesResult)
          ? tradesResult
          : [],
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to load Paper Trading data.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    Promise.resolve().then(() => {
      loadPaperTradingData()
    })
  }, [loadPaperTradingData])

  async function handleStartReplay() {
    if (starting || resetting) {
      return
    }

    setStarting(true)
    setError(null)

    try {
      await startPaperTrading()
      await loadPaperTradingData()
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Paper Trading replay failed.',
      )
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
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to reset Paper Trading.',
      )
    } finally {
      setResetting(false)
    }
  }

  const displayReport = report || {
    starting_capital: 100000,
    ending_equity: 100000,
    realized_pnl: 0,
    total_transaction_cost: 0,
    trade_count: 0,
    winning_trades: 0,
    losing_trades: 0,
    gross_profit: 0,
    gross_loss: 0,
    long_trades: 0,
    short_trades: 0,
    net_return_pct: 0,
    win_rate_pct: 0,
    profit_factor: 0,
  }

  const displayStatus = status || {
    active: false,
    has_position: false,
    trade_count: 0,
    starting_capital: 100000,
    realized_pnl: 0,
    current_equity: 100000,
    total_transaction_cost: 0,
  }

  const isBusy = loading || starting || resetting

  const sessionLabel = starting
    ? 'REPLAYING'
    : resetting
      ? 'RESETTING'
      : displayStatus.active
        ? 'ACTIVE'
        : 'READY'

  const sessionClass = starting
    ? 'replaying'
    : resetting
      ? 'resetting'
      : displayStatus.active
        ? 'active'
        : 'ready'

  const returnClass = getPnlClass(
    displayReport.net_return_pct,
  )

  const pnlClass = getPnlClass(
    displayReport.realized_pnl,
  )

  const equityChange =
    typeof displayReport.ending_equity === 'number' &&
    typeof displayReport.starting_capital === 'number'
      ? displayReport.ending_equity -
        displayReport.starting_capital
      : null

  const equityChangeClass =
    equityChange !== null
      ? getPnlClass(equityChange)
      : ''

  const recentTrades = useMemo(
    () => [...trades].reverse(),
    [trades],
  )

  return (
    <div className="paper-trading-view">
      <div className="paper-page-header">
        <div>
          <span className="paper-page-kicker">
            PAPER TRADING
          </span>

          <h1>Paper Trading</h1>

          <p>
            Test the frozen SignalForge strategy against
            real historical NIFTY 1-minute data.
          </p>
        </div>

        <div className="paper-page-actions">
          <span className="paper-mode-badge-large">
            <span className="paper-mode-dot" />
            PAPER MODE
          </span>

          <span className={`paper-session-badge ${sessionClass}`}>
            <span />
            {sessionLabel}
          </span>
        </div>
      </div>

      {loading && !status && !report ? (
        <LoadingState
          title="Loading Paper Trading Session..."
          description="Connecting to simulation engine and retrieving trade telemetry..."
        />
      ) : error && !status && !report ? (
        <ErrorState
          title="Paper Trading System Offline"
          message={error}
          onRetry={loadPaperTradingData}
          retryLabel="Retry Connection"
        />
      ) : (
        <>
          {error && (
            <div className="paper-error-banner" role="alert">
              <div className="paper-error-icon">!</div>

              <div>
                <strong>Paper Trading API unavailable</strong>
                <span>{error}</span>
              </div>

              <button
                type="button"
                onClick={loadPaperTradingData}
                disabled={isBusy}
              >
                Retry
              </button>
            </div>
          )}

          <section className="paper-stats-grid">
        <StatCard
          label="Starting Capital"
          value={formatCurrency(
            displayReport.starting_capital,
          )}
          subValue="Initial paper capital"
          className="capital"
        />

        <StatCard
          label="Current Equity"
          value={formatCurrency(
            displayReport.ending_equity,
          )}
          subValue={
            equityChange !== null
              ? `${equityChange >= 0 ? '+' : ''}${formatCurrency(equityChange)}`
              : '—'
          }
          className={
            equityChangeClass
              ? `equity ${equityChangeClass}`
              : 'equity'
          }
        />

        <StatCard
          label="Realized P&L"
          value={formatCurrency(
            displayReport.realized_pnl,
          )}
          subValue={formatPercent(
            displayReport.net_return_pct,
          )}
          className={`pnl ${pnlClass}`}
        />

        <StatCard
          label="Return"
          value={formatPercent(
            displayReport.net_return_pct,
          )}
          subValue="Based on starting capital"
          className={`return ${returnClass}`}
        />
      </section>

      <section className="paper-secondary-stats">
        <StatCard
          label="Trade Count"
          value={formatNumber(
            displayReport.trade_count,
            0,
          )}
          subValue={`${displayReport.long_trades} long · ${displayReport.short_trades} short`}
        />

        <StatCard
          label="Win Rate"
          value={formatPercent(
            displayReport.win_rate_pct,
          )}
          subValue={`${displayReport.winning_trades} wins · ${displayReport.losing_trades} losses`}
        />

        <StatCard
          label="Profit Factor"
          value={
            Number.isFinite(
              displayReport.profit_factor,
            )
              ? formatNumber(
                  displayReport.profit_factor,
                  2,
                )
              : '∞'
          }
          subValue="Gross profit / gross loss"
        />

        <StatCard
          label="Transaction Costs"
          value={formatCurrency(
            displayReport.total_transaction_cost,
          )}
          subValue="Entry + exit costs"
        />
      </section>

      <section className="paper-session-panel">
        <SectionHeader
          title="Session Controls"
          subtitle="Run a deterministic replay using the recent NIFTY 1-minute dataset."
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

                <span>
                  {starting
                    ? 'Running Replay…'
                    : 'Start Replay'}
                </span>
              </button>

              <button
                type="button"
                className="paper-reset-button"
                onClick={handleReset}
                disabled={isBusy}
              >
                <span>↻</span>

                {resetting
                  ? 'Resetting…'
                  : 'Reset'}
              </button>
            </div>
          }
        />

        <div className="paper-session-meta">
          <div className="paper-session-status">
            <span
              className={`paper-status-indicator ${sessionClass}`}
            />

            <div>
              <span>Session Status</span>
              <strong>{sessionLabel}</strong>
            </div>
          </div>

          <div className="paper-session-stat">
            <span>Open Position</span>

            <strong>
              {displayStatus.has_position
                ? 'YES'
                : 'NO'}
            </strong>
          </div>

          <div className="paper-session-stat">
            <span>Trades</span>

            <strong className="tabular-num">
              {displayStatus.trade_count}
            </strong>
          </div>

          <div className="paper-session-stat">
            <span>Current Equity</span>

            <strong className="tabular-num">
              {formatCurrency(
                displayStatus.current_equity,
              )}
            </strong>
          </div>

          <div className="paper-session-stat">
            <span>Realized P&L</span>

            <strong
              className={`tabular-num ${getPnlClass(displayStatus.realized_pnl)}`}
            >
              {formatCurrency(
                displayStatus.realized_pnl,
              )}
            </strong>
          </div>
        </div>
      </section>

      <section className="paper-trades-panel">
        <SectionHeader
          title="Recent Paper Trades"
          subtitle="Completed trades generated by the causal SignalForge strategy."
          right={
            <span className="paper-trade-count">
              {recentTrades.length} trades
            </span>
          }
        />

        <div className="paper-table-scroll">
          <div className="paper-trades-table">
            <div className="paper-table-head">
              <span>#</span>
              <span>Position</span>
              <span>Entry Time</span>
              <span>Exit Time</span>

              <span className="text-right">
                Entry Price
              </span>

              <span className="text-right">
                Exit Price
              </span>

              <span className="text-right">
                Qty
              </span>

              <span className="text-right">
                Gross P&L
              </span>

              <span className="text-right">
                Costs
              </span>

              <span className="text-right">
                Net P&L
              </span>

              <span className="text-right">
                Return
              </span>

              <span>Reason</span>
            </div>

            {recentTrades.length === 0 ? (
              <EmptyState
                title="No Paper Trades Yet"
                description="Start a simulation replay to execute trades against frozen historical data."
                action={
                  <button
                    type="button"
                    className="sf-state-retry-btn"
                    onClick={handleStartReplay}
                    disabled={starting || resetting}
                  >
                    {starting ? 'Starting Simulation...' : 'Start Simulation Replay'}
                  </button>
                }
              />
            ) : (
              recentTrades.map((trade, index) => {
                const netPnlClass =
                  getPnlClass(trade.net_pnl)

                const position =
                  getPositionLabel(
                    trade.position,
                  )

                return (
                  <div
                    className="paper-trade-row"
                    key={`${trade.entry_time}-${index}`}
                  >
                    <span className="paper-trade-number">
                      {index + 1}
                    </span>

                    <span>
                      <strong
                        className={`paper-position ${position.toLowerCase()}`}
                      >
                        {position}
                      </strong>
                    </span>

                    <span className="tabular-num">
                      {formatTimestamp(
                        trade.entry_time,
                      )}
                    </span>

                    <span className="tabular-num">
                      {formatTimestamp(
                        trade.exit_time,
                      )}
                    </span>

                    <span className="text-right tabular-num">
                      {formatCurrency(
                        trade.entry_price,
                      )}
                    </span>

                    <span className="text-right tabular-num">
                      {formatCurrency(
                        trade.exit_price,
                      )}
                    </span>

                    <span className="text-right tabular-num">
                      {trade.quantity}
                    </span>

                    <span className="text-right tabular-num">
                      {formatCurrency(
                        trade.gross_pnl,
                      )}
                    </span>

                    <span className="text-right tabular-num paper-cost">
                      {formatCurrency(
                        trade.transaction_cost,
                      )}
                    </span>

                    <strong
                      className={`text-right tabular-num ${netPnlClass}`}
                    >
                      {formatCurrency(
                        trade.net_pnl,
                      )}
                    </strong>

                    <span
                      className={`text-right tabular-num ${netPnlClass}`}
                    >
                      {formatPercent(
                        trade.return_pct,
                      )}
                    </span>

                    <span
                      className="paper-trade-reason"
                      title={trade.reason || ''}
                    >
                      {trade.reason || '—'}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </section>

      <section className="paper-disclosure-panel">
        <div className="paper-disclosure-icon">
          i
        </div>

        <div>
          <strong>Paper Trading only</strong>

          <p>
            This workspace uses historical market data
            and the frozen SignalForge strategy. It does
            not place broker orders or use real money.
          </p>
        </div>

        <div className="paper-disclosure-source">
          <span>Data</span>
          <strong>NIFTY 1-minute historical</strong>
        </div>
          </section>
        </>
      )}
    </div>
  )
}

export default PaperTradingView