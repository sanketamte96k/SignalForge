import React, { useMemo, useState } from 'react'
import './BacktestAnalyticsModal.css'
import { getBacktestTearsheetUrl } from './api'

function formatCurrency(val) {
  if (typeof val !== 'number' || Number.isNaN(val)) return '₹0.00'
  return `₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function BacktestAnalyticsModal({ isOpen, onClose, result }) {
  if (!isOpen || !result) return null

  const [activeTab, setActiveTab] = useState('equity')
  const [tradeFilter, setTradeFilter] = useState('ALL')
  const [tradeSort, setTradeSort] = useState('date_asc')
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [hoverEquityPoint, setHoverEquityPoint] = useState(null)
  const [hoverDrawdownPoint, setHoverDrawdownPoint] = useState(null)

  const initialCapital = Number(result.portfolio?.initial_capital || 100000)
  const trades = result.trades || []
  const metrics = result.metrics || {}
  const dateRange = result.date_range || {}
  const symbol = result.symbol || 'NIFTY 50'
  const isCausal = result.execution_model === 'next_open'

  // Construct Chronological Equity Progression & Drawdown Curve
  const equityCurve = useMemo(() => {
    const curve = [
      {
        step: 0,
        timestamp: dateRange.start ? String(dateRange.start).slice(0, 16) : 'Start',
        trade_id: null,
        side: null,
        net_pnl: 0,
        equity: initialCapital,
        peak_equity: initialCapital,
        drawdown: 0,
        drawdown_pct: 0,
      },
    ]

    let current = initialCapital
    let peak = initialCapital

    trades.forEach((t, i) => {
      const net = Number(t.net_pnl || 0)
      current += net
      if (current > peak) {
        peak = current
      }
      const dd = current - peak
      const ddPct = peak > 0 ? (dd / peak) * 100 : 0

      curve.push({
        step: i + 1,
        timestamp: t.exit_time ? String(t.exit_time).slice(0, 16) : `Trade ${i + 1}`,
        trade_id: t.trade_id || i + 1,
        side: t.side,
        net_pnl: net,
        equity: Math.round(current * 100) / 100,
        peak_equity: Math.round(peak * 100) / 100,
        drawdown: Math.round(dd * 100) / 100,
        drawdown_pct: Math.round(ddPct * 100) / 100,
      })
    })

    return curve
  }, [trades, initialCapital, dateRange])

  // Filter and Sort Trade Records
  const filteredSortedTrades = useMemo(() => {
    let list = [...trades]

    if (tradeFilter === 'WIN') {
      list = list.filter((t) => Number(t.net_pnl || 0) > 0)
    } else if (tradeFilter === 'LOSS') {
      list = list.filter((t) => Number(t.net_pnl || 0) < 0)
    } else if (tradeFilter === 'BUY') {
      list = list.filter((t) => String(t.side).toUpperCase().includes('BUY') || String(t.side).toUpperCase().includes('LONG'))
    } else if (tradeFilter === 'SELL') {
      list = list.filter((t) => String(t.side).toUpperCase().includes('SELL') || String(t.side).toUpperCase().includes('SHORT'))
    }

    list.sort((a, b) => {
      if (tradeSort === 'date_desc') return (b.trade_id || 0) - (a.trade_id || 0)
      if (tradeSort === 'date_asc') return (a.trade_id || 0) - (b.trade_id || 0)
      if (tradeSort === 'pnl_desc') return Number(b.net_pnl || 0) - Number(a.net_pnl || 0)
      if (tradeSort === 'pnl_asc') return Number(a.net_pnl || 0) - Number(b.net_pnl || 0)
      if (tradeSort === 'ret_desc') return Number(b.return_pct || 0) - Number(a.return_pct || 0)
      if (tradeSort === 'ret_asc') return Number(a.return_pct || 0) - Number(b.return_pct || 0)
      return 0
    })

    return list
  }, [trades, tradeFilter, tradeSort])

  const totalPages = Math.max(1, Math.ceil(filteredSortedTrades.length / pageSize))
  const displayedTrades = filteredSortedTrades.slice((page - 1) * pageSize, page * pageSize)

  // SVG Chart Geometry
  const width = 840
  const heightEq = 240
  const heightDd = 140
  const padL = 70
  const padR = 24
  const padT = 24
  const padB = 32

  const plotWEq = width - padL - padR
  const plotHEq = heightEq - padT - padB

  const equities = equityCurve.map((p) => p.equity)
  const minEq = Math.min(...equities)
  const maxEq = Math.max(...equities)
  const spanEq = Math.max(1, maxEq - minEq)
  const yMinEq = minEq - spanEq * 0.08
  const yMaxEq = maxEq + spanEq * 0.08

  const toXEq = (step) => {
    if (equityCurve.length <= 1) return padL + plotWEq / 2
    return padL + (step / (equityCurve.length - 1)) * plotWEq
  }

  const toYEq = (val) => {
    const norm = (val - yMinEq) / (yMaxEq - yMinEq)
    return padT + (1 - norm) * plotHEq
  }

  const eqPts = equityCurve.map((pt) => [toXEq(pt.step), toYEq(pt.equity)])
  const eqLinePath = eqPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const eqAreaPath = eqPts.length
    ? `${eqLinePath} L ${eqPts[eqPts.length - 1][0].toFixed(1)},${(padT + plotHEq).toFixed(1)} L ${eqPts[0][0].toFixed(1)},${(padT + plotHEq).toFixed(1)} Z`
    : ''

  // Drawdown Geometry
  const plotHDd = heightDd - padT - padB
  const dds = equityCurve.map((p) => p.drawdown_pct)
  const minDd = Math.min(...dds)
  const yMinDd = Math.min(-0.1, minDd * 1.15)
  const yMaxDd = 0.0

  const toYDd = (val) => {
    const norm = (val - yMinDd) / (yMaxDd - yMinDd)
    return padT + (1 - norm) * plotHDd
  }

  const ddPts = equityCurve.map((pt) => [toXEq(pt.step), toYDd(pt.drawdown_pct)])
  const ddLinePath = ddPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const zeroYDd = toYDd(0.0)
  const ddAreaPath = ddPts.length
    ? `${ddLinePath} L ${ddPts[ddPts.length - 1][0].toFixed(1)},${zeroYDd.toFixed(1)} L ${ddPts[0][0].toFixed(1)},${zeroYDd.toFixed(1)} Z`
    : ''

  return (
    <div className="bam-overlay" role="dialog" aria-modal="true" aria-labelledby="bam-modal-title">
      <div className="bam-container">
        {/* Header */}
        <div className="bam-header">
          <div className="bam-title-wrap">
            <h2 id="bam-modal-title" className="bam-title">
              Quantitative Backtest Analytics — {symbol}
            </h2>
            <span className={`bam-badge ${isCausal ? 'bam-badge-causal' : 'bam-badge-theoretical'}`}>
              {isCausal ? 'Causal Next-Open' : 'Theoretical Lookahead'}
            </span>
          </div>

          <div className="bam-header-actions">
            <a
              href={getBacktestTearsheetUrl(result.job_id)}
              target="_blank"
              rel="noopener noreferrer"
              className="bam-btn-secondary"
              title="Open full self-contained research report in a new tab"
            >
              <span>📑 Tearsheet</span>
            </a>
            <a
              href={getBacktestTearsheetUrl(result.job_id, true)}
              className="bam-btn-secondary"
              title="Download standalone HTML report"
            >
              <span>⬇️ Download</span>
            </a>
            <button type="button" className="bam-btn-close" onClick={onClose} aria-label="Close analytics modal">
              ✕
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bam-nav" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'equity'}
            className={`bam-tab ${activeTab === 'equity' ? 'active' : ''}`}
            onClick={() => setActiveTab('equity')}
          >
            📊 Equity & Drawdown
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'trades'}
            className={`bam-tab ${activeTab === 'trades' ? 'active' : ''}`}
            onClick={() => setActiveTab('trades')}
          >
            📋 Trade History ({trades.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'metrics'}
            className={`bam-tab ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            📈 Extended Metrics
          </button>
        </div>

        {/* Content Body */}
        <div className="bam-body">
          {/* Top KPI Cards (Always visible) */}
          <div className="bam-kpi-grid">
            <div className="bam-kpi-card">
              <div className="bam-kpi-label">Net Return</div>
              <div className={`bam-kpi-val ${metrics.total_return_pct >= 0 ? 'bam-val-pos' : 'bam-val-neg'}`}>
                {metrics.total_return_pct >= 0 ? '+' : ''}
                {metrics.total_return_pct}%
              </div>
              <div className="bam-kpi-sub">P&L: {formatCurrency(metrics.total_pnl)}</div>
            </div>
            <div className="bam-kpi-card">
              <div className="bam-kpi-label">Win Rate</div>
              <div className="bam-kpi-val bam-val-neutral">{metrics.win_rate_pct}%</div>
              <div className="bam-kpi-sub">
                {metrics.winning_trades}W / {metrics.losing_trades}L
              </div>
            </div>
            <div className="bam-kpi-card">
              <div className="bam-kpi-label">Profit Factor</div>
              <div className="bam-kpi-val bam-val-neutral">{metrics.profit_factor}</div>
              <div className="bam-kpi-sub">Expectancy: {formatCurrency(metrics.expectancy)}</div>
            </div>
            <div className="bam-kpi-card">
              <div className="bam-kpi-label">Max Drawdown</div>
              <div className="bam-kpi-val bam-val-neg">-{metrics.max_drawdown_pct}%</div>
              <div className="bam-kpi-sub">Peak: {formatCurrency(result.portfolio?.peak_equity)}</div>
            </div>
            <div className="bam-kpi-card">
              <div className="bam-kpi-label">Final Equity</div>
              <div className="bam-kpi-val bam-val-neutral">{formatCurrency(result.portfolio?.final_equity)}</div>
              <div className="bam-kpi-sub">Start: {formatCurrency(initialCapital)}</div>
            </div>
          </div>

          {/* Tab 1: Equity & Drawdown Curves */}
          {activeTab === 'equity' && (
            <div>
              {/* Equity Curve SVG */}
              <div className="bam-chart-box">
                <div className="bam-chart-header">
                  <div className="bam-chart-title">
                    <span>📈 Account Equity Progression</span>
                  </div>
                  <div className="bam-chart-meta">
                    {hoverEquityPoint ? (
                      <span style={{ color: '#00eaaf' }}>
                        {hoverEquityPoint.trade_id ? `Trade #${hoverEquityPoint.trade_id}` : 'Start'} (
                        {hoverEquityPoint.timestamp}) : {formatCurrency(hoverEquityPoint.equity)} (Net:{' '}
                        {hoverEquityPoint.net_pnl >= 0 ? '+' : ''}
                        {formatCurrency(hoverEquityPoint.net_pnl)})
                      </span>
                    ) : (
                      <span>Hover point for trade details</span>
                    )}
                  </div>
                </div>

                <div style={{ width: '100%', overflowX: 'auto' }}>
                  <svg
                    viewBox={`0 0 ${width} ${heightEq}`}
                    style={{ width: '100%', height: 'auto', background: '#060d15', borderRadius: 4 }}
                    role="img"
                    aria-label="Account equity progression chart"
                  >
                    <defs>
                      <linearGradient id="bamEqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#00eaaf" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#00eaaf" stopOpacity="0.02" />
                      </linearGradient>
                    </defs>

                    {/* Y-axis Ticks */}
                    {[0, 0.33, 0.66, 1].map((f, i) => {
                      const v = yMinEq + (yMaxEq - yMinEq) * f
                      const yPos = toYEq(v)
                      return (
                        <g key={i}>
                          <line
                            x1={padL}
                            y1={yPos}
                            x2={width - padR}
                            y2={yPos}
                            stroke="#132333"
                            strokeWidth="1"
                            strokeDasharray="3,3"
                          />
                          <text x={padL - 8} y={yPos + 4} fill="#637d94" fontSize="10" textAnchor="end" fontFamily="monospace">
                            ₹{v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </text>
                        </g>
                      )
                    })}

                    {/* Starting Capital Baseline */}
                    <line
                      x1={padL}
                      y1={toYEq(initialCapital)}
                      x2={width - padR}
                      y2={toYEq(initialCapital)}
                      stroke="#f0b90b"
                      strokeWidth="1"
                      strokeDasharray="4,4"
                      opacity="0.6"
                    />

                    {/* Area & Line */}
                    {eqAreaPath && <path d={eqAreaPath} fill="url(#bamEqGrad)" />}
                    {eqLinePath && (
                      <path d={eqLinePath} fill="none" stroke="#00eaaf" strokeWidth="2.2" strokeLinejoin="round" />
                    )}

                    {/* Interactive Circles */}
                    {equityCurve.map((pt, i) => {
                      const cx = toXEq(pt.step)
                      const cy = toYEq(pt.equity)
                      return (
                        <circle
                          key={i}
                          cx={cx}
                          cy={cy}
                          r={hoverEquityPoint?.step === pt.step ? 5 : 3.5}
                          fill={hoverEquityPoint?.step === pt.step ? '#ffffff' : '#00eaaf'}
                          stroke="#060d15"
                          strokeWidth="1.5"
                          style={{ cursor: 'pointer' }}
                          onMouseEnter={() => setHoverEquityPoint(pt)}
                          onMouseLeave={() => setHoverEquityPoint(null)}
                        >
                          <title>
                            {`${pt.trade_id ? `Trade #${pt.trade_id}` : 'Start'}: ${pt.timestamp} | Equity: ₹${pt.equity} | Net: ₹${pt.net_pnl}`}
                          </title>
                        </circle>
                      )
                    })}
                  </svg>
                </div>
              </div>

              {/* Drawdown SVG */}
              <div className="bam-chart-box">
                <div className="bam-chart-header">
                  <div className="bam-chart-title">
                    <span>📉 Underwater Drawdown Curve (%)</span>
                  </div>
                  <div className="bam-chart-meta">
                    {hoverDrawdownPoint ? (
                      <span style={{ color: '#ff6876' }}>
                        {hoverDrawdownPoint.trade_id ? `Trade #${hoverDrawdownPoint.trade_id}` : 'Start'}: {hoverDrawdownPoint.drawdown_pct}% ({formatCurrency(hoverDrawdownPoint.drawdown)})
                      </span>
                    ) : (
                      <span>Max Drawdown: -{metrics.max_drawdown_pct}%</span>
                    )}
                  </div>
                </div>

                <div style={{ width: '100%', overflowX: 'auto' }}>
                  <svg
                    viewBox={`0 0 ${width} ${heightDd}`}
                    style={{ width: '100%', height: 'auto', background: '#060d15', borderRadius: 4 }}
                    role="img"
                    aria-label="Underwater drawdown percentage chart"
                  >
                    <defs>
                      <linearGradient id="bamDdGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ff6876" stopOpacity="0.05" />
                        <stop offset="100%" stopColor="#ff6876" stopOpacity="0.3" />
                      </linearGradient>
                    </defs>

                    {/* Y-axis Ticks */}
                    {[0, 0.5, 1].map((f, i) => {
                      const v = yMaxDd - (yMaxDd - yMinDd) * f
                      const yPos = toYDd(v)
                      return (
                        <g key={i}>
                          <line
                            x1={padL}
                            y1={yPos}
                            x2={width - padR}
                            y2={yPos}
                            stroke="#132333"
                            strokeWidth="1"
                            strokeDasharray="3,3"
                          />
                          <text x={padL - 8} y={yPos + 4} fill="#637d94" fontSize="10" textAnchor="end" fontFamily="monospace">
                            {v.toFixed(2)}%
                          </text>
                        </g>
                      )
                    })}

                    {/* Underwater Area & Line */}
                    {ddAreaPath && <path d={ddAreaPath} fill="url(#bamDdGrad)" />}
                    {ddLinePath && (
                      <path d={ddLinePath} fill="none" stroke="#ff6876" strokeWidth="1.8" strokeLinejoin="round" />
                    )}

                    {/* Interactive Circles */}
                    {equityCurve.map((pt, i) => {
                      const cx = toXEq(pt.step)
                      const cy = toYDd(pt.drawdown_pct)
                      return (
                        <circle
                          key={i}
                          cx={cx}
                          cy={cy}
                          r={hoverDrawdownPoint?.step === pt.step ? 4.5 : 3}
                          fill={hoverDrawdownPoint?.step === pt.step ? '#ffffff' : '#ff6876'}
                          stroke="#060d15"
                          strokeWidth="1"
                          style={{ cursor: 'pointer' }}
                          onMouseEnter={() => setHoverDrawdownPoint(pt)}
                          onMouseLeave={() => setHoverDrawdownPoint(null)}
                        >
                          <title>
                            {`${pt.trade_id ? `Trade #${pt.trade_id}` : 'Start'}: ${pt.drawdown_pct}% (${formatCurrency(pt.drawdown)})`}
                          </title>
                        </circle>
                      )
                    })}
                  </svg>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Trade History */}
          {activeTab === 'trades' && (
            <div>
              {/* Toolbar */}
              <div className="bam-table-toolbar">
                <div className="bam-filter-group">
                  <button
                    type="button"
                    className={`bam-pill-btn ${tradeFilter === 'ALL' ? 'active' : ''}`}
                    onClick={() => {
                      setTradeFilter('ALL')
                      setPage(1)
                    }}
                  >
                    ALL ({trades.length})
                  </button>
                  <button
                    type="button"
                    className={`bam-pill-btn ${tradeFilter === 'WIN' ? 'active' : ''}`}
                    onClick={() => {
                      setTradeFilter('WIN')
                      setPage(1)
                    }}
                  >
                    WINNERS ({metrics.winning_trades || 0})
                  </button>
                  <button
                    type="button"
                    className={`bam-pill-btn ${tradeFilter === 'LOSS' ? 'active' : ''}`}
                    onClick={() => {
                      setTradeFilter('LOSS')
                      setPage(1)
                    }}
                  >
                    LOSERS ({metrics.losing_trades || 0})
                  </button>
                  <button
                    type="button"
                    className={`bam-pill-btn ${tradeFilter === 'BUY' ? 'active' : ''}`}
                    onClick={() => {
                      setTradeFilter('BUY')
                      setPage(1)
                    }}
                  >
                    LONG / BUY
                  </button>
                  <button
                    type="button"
                    className={`bam-pill-btn ${tradeFilter === 'SELL' ? 'active' : ''}`}
                    onClick={() => {
                      setTradeFilter('SELL')
                      setPage(1)
                    }}
                  >
                    SHORT / SELL
                  </button>
                </div>

                <div className="bam-sort-group">
                  <span>Sort by:</span>
                  <select
                    className="bam-select"
                    value={tradeSort}
                    onChange={(e) => {
                      setTradeSort(e.target.value)
                      setPage(1)
                    }}
                  >
                    <option value="date_asc">Trade # (Ascending)</option>
                    <option value="date_desc">Trade # (Descending)</option>
                    <option value="pnl_desc">Net P&L (High to Low)</option>
                    <option value="pnl_asc">Net P&L (Low to High)</option>
                    <option value="ret_desc">Return % (High to Low)</option>
                    <option value="ret_asc">Return % (Low to High)</option>
                  </select>
                </div>
              </div>

              {/* Table */}
              <div className="bam-table-wrap">
                <table className="bam-table">
                  <thead>
                    <tr>
                      <th className="bam-text-center">#</th>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th>Entry Time</th>
                      <th className="bam-text-right">Entry Price</th>
                      <th>Exit Time</th>
                      <th className="bam-text-right">Exit Price</th>
                      <th className="bam-text-center">Qty</th>
                      <th className="bam-text-right">Gross P&L</th>
                      <th className="bam-text-right">Costs</th>
                      <th className="bam-text-right">Net P&L</th>
                      <th className="bam-text-right">Return %</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedTrades.length > 0 ? (
                      displayedTrades.map((t) => {
                        const net = Number(t.net_pnl || 0)
                        const gross = Number(t.gross_pnl || 0)
                        const costs = Number(t.costs || 0)
                        const ret = Number(t.return_pct || 0)
                        const isBuy = String(t.side).toUpperCase().includes('BUY') || String(t.side).toUpperCase().includes('LONG')

                        return (
                          <tr key={t.trade_id}>
                            <td className="bam-text-center bam-font-mono">{t.trade_id}</td>
                            <td>
                              <strong>{symbol}</strong>
                            </td>
                            <td>
                              <span className={isBuy ? 'bam-side-buy' : 'bam-side-sell'}>{t.side}</span>
                            </td>
                            <td className="bam-font-mono">{String(t.entry_time).slice(0, 16)}</td>
                            <td className="bam-font-mono bam-text-right">{formatCurrency(t.entry_price)}</td>
                            <td className="bam-font-mono">{String(t.exit_time).slice(0, 16)}</td>
                            <td className="bam-font-mono bam-text-right">{formatCurrency(t.exit_price)}</td>
                            <td className="bam-text-center bam-font-mono">{t.quantity}</td>
                            <td
                              className={`bam-font-mono bam-text-right ${gross > 0 ? 'bam-val-pos' : gross < 0 ? 'bam-val-neg' : ''}`}
                            >
                              {gross >= 0 ? '+' : ''}
                              {formatCurrency(gross)}
                            </td>
                            <td className="bam-font-mono bam-text-right">{formatCurrency(costs)}</td>
                            <td
                              className={`bam-font-mono bam-text-right ${net > 0 ? 'bam-val-pos' : net < 0 ? 'bam-val-neg' : ''}`}
                              style={{ fontWeight: 'bold' }}
                            >
                              {net >= 0 ? '+' : ''}
                              {formatCurrency(net)}
                            </td>
                            <td
                              className={`bam-font-mono bam-text-right ${ret > 0 ? 'bam-val-pos' : ret < 0 ? 'bam-val-neg' : ''}`}
                            >
                              {ret >= 0 ? '+' : ''}
                              {ret.toFixed(2)}%
                            </td>
                            <td>
                              <span style={{ fontSize: '10px', color: '#88a3b8' }}>{t.exit_reason || 'SIGNAL'}</span>
                            </td>
                          </tr>
                        )
                      })
                    ) : (
                      <tr>
                        <td colSpan="13" className="bam-empty-box">
                          No trades matching the selected filter criteria.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="bam-pagination">
                  <div>
                    Showing {(page - 1) * pageSize + 1} to{' '}
                    {Math.min(page * pageSize, filteredSortedTrades.length)} of {filteredSortedTrades.length} trades
                  </div>
                  <div className="bam-page-btns">
                    <button
                      type="button"
                      className="bam-pill-btn"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </button>
                    <span style={{ padding: '4px 8px' }}>
                      {page} / {totalPages}
                    </span>
                    <button
                      type="button"
                      className="bam-pill-btn"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Extended Research Metrics */}
          {activeTab === 'metrics' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
              <div className="bam-chart-box">
                <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#00eaaf', marginBottom: '8px' }}>
                  PROFITABILITY & EXPECTANCY
                </div>
                <div style={{ fontSize: '11px', lineHeight: '1.8' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Total Trades:</span>
                    <strong>{metrics.total_trades}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Winning Trades:</span>
                    <strong style={{ color: '#00eaaf' }}>{metrics.winning_trades}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Losing Trades:</span>
                    <strong style={{ color: '#ff6876' }}>{metrics.losing_trades}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Win Rate:</span>
                    <strong>{metrics.win_rate_pct}%</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Average Win:</span>
                    <strong style={{ color: '#00eaaf' }}>{formatCurrency(metrics.average_win)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Average Loss:</span>
                    <strong style={{ color: '#ff6876' }}>{formatCurrency(metrics.average_loss)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Expectancy per Trade:</span>
                    <strong>{formatCurrency(metrics.expectancy)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Profit Factor:</span>
                    <strong>{metrics.profit_factor}</strong>
                  </div>
                </div>
              </div>

              <div className="bam-chart-box">
                <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#7cb5ec', marginBottom: '8px' }}>
                  CAPITAL & DRAWDOWN RISK
                </div>
                <div style={{ fontSize: '11px', lineHeight: '1.8' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Starting Capital:</span>
                    <strong>{formatCurrency(initialCapital)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Peak Account Equity:</span>
                    <strong>{formatCurrency(result.portfolio?.peak_equity)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Final Account Equity:</span>
                    <strong>{formatCurrency(result.portfolio?.final_equity)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Max Drawdown (%):</span>
                    <strong style={{ color: '#ff6876' }}>-{metrics.max_drawdown_pct}%</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Total Net P&L:</span>
                    <strong style={{ color: metrics.total_pnl >= 0 ? '#00eaaf' : '#ff6876' }}>
                      {formatCurrency(metrics.total_pnl)}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Total Return:</span>
                    <strong style={{ color: metrics.total_return_pct >= 0 ? '#00eaaf' : '#ff6876' }}>
                      {metrics.total_return_pct}%
                    </strong>
                  </div>
                </div>
              </div>

              <div className="bam-chart-box">
                <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#f0b90b', marginBottom: '8px' }}>
                  PROVENANCE & METHODOLOGY
                </div>
                <div style={{ fontSize: '11px', lineHeight: '1.8' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Execution Model:</span>
                    <strong>{result.execution_model}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Dataset Candles:</span>
                    <strong>{dateRange.total_candles || '-'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>Job ID:</span>
                    <strong style={{ fontFamily: 'monospace' }}>{result.job_id}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#88a3b8' }}>V1 Config Hash:</span>
                    <strong style={{ fontFamily: 'monospace' }}>920515d7...</strong>
                  </div>
                  <div style={{ marginTop: '8px', color: '#88a3b8', fontSize: '10px', fontStyle: 'italic' }}>
                    * Quantitative research simulation only. Zero broker connectivity.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
