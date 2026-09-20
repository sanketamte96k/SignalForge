import React, { useState, useEffect, useMemo } from 'react'
import './MarketIntelligenceView.css'
import {
  fetchIntelligenceOverview,
  fetchScannedOpportunities,
  fetchSymbolIntelligence,
} from './api'

// Fallback mock opportunities for preview / testing if backend offline
const FALLBACK_OPPORTUNITIES = [
  {
    symbol: 'RELIANCE',
    timestamp: '2018-06-15 11:30:00',
    price: 985.4,
    direction: 'LONG_BIAS',
    opportunity_score: 78.4,
    tradeability_score: 81.2,
    confidence_score: 76.0,
    risk_level: 'MEDIUM',
    decision: 'TRADEABLE',
    market_condition: 'TRENDING',
    trend: {
      direction: 'LONG_BIAS',
      state: 'BULLISH',
      strength: 74.0,
      ema9: 984.2,
      ema21: 981.1,
      ema50: 975.4,
      price_to_ema21_pct: 0.44,
      ema21_slope: 0.018,
      reasons: ['Price is above EMA21 by +0.44%', 'Fast EMA9 stacked above medium EMA21'],
    },
    volatility: {
      state: 'NORMAL',
      dynamics: 'STABLE',
      atr: 1.25,
      atr_relative_ratio: 1.05,
      realized_volatility_pctile: 52.0,
      volatility_quality_score: 90.0,
      reasons: ['Normal balanced volatility regime', 'Volatility trajectory is stable'],
    },
    momentum: {
      direction: 'LONG_BIAS',
      strength: 68.0,
      rsi14: 58.4,
      return_5m_pct: 0.12,
      return_15m_pct: 0.35,
      return_30m_pct: 0.62,
      roc: 0.28,
      reasons: ['Short & medium-term returns aligned positive', 'RSI in healthy bullish expansion zone'],
    },
    structure: {
      state: 'BULLISH_STRUCTURE',
      quality_score: 80.0,
      recent_swing_high: 988.0,
      recent_swing_low: 978.5,
      range_position: 0.73,
      breakout_state: 'WITHIN_RANGE',
      reasons: ['Clean bullish structural progression: Higher Highs and Higher Lows confirmed'],
    },
    session: {
      state: 'EARLY_SESSION',
      minutes_from_open: 135,
      minutes_to_close: 240,
      session_quality_score: 90.0,
      reasons: ['Prime early session liquidity window'],
    },
    risk: {
      risk_level: 'MEDIUM',
      suggested_risk_distance: 2.1,
      risk_distance_atr_multiple: 1.68,
      estimated_reward_risk_ratio: 1.5,
      risk_quality_score: 70.0,
      warnings: [],
    },
    confidence: {
      score: 76.0,
      agreement_ratio: 1.0,
      conflicting_factors: [],
    },
    explanation: {
      summary: 'RELIANCE at Rs. 985.40 presents a LONG BIAS opportunity (Score: 78/100, Confidence: 76/100) with orderly risk context.',
      evidence: [
        'Trend: Strong bullish alignment (EMA9 > EMA21 > EMA50; strength 74)',
        'Momentum: Positive directional velocity (RSI 58.4, 5m +0.12%)',
        'Structure: Bullish Structure (Range pos: 73%)',
        'Volatility: Balanced and orderly ATR regime (1.25, STABLE)',
      ],
      warnings: ['Resistance: Price pressing immediate range ceiling'],
      no_trade_reasons: [],
    },
  },
  {
    symbol: 'TCS',
    timestamp: '2018-06-15 11:30:00',
    price: 1342.5,
    direction: 'SHORT_BIAS',
    opportunity_score: 71.5,
    tradeability_score: 74.0,
    confidence_score: 72.0,
    risk_level: 'LOW',
    decision: 'TRADEABLE',
    market_condition: 'TRENDING',
    trend: {
      direction: 'SHORT_BIAS',
      state: 'BEARISH',
      strength: 68.0,
      ema9: 1344.0,
      ema21: 1348.5,
      ema50: 1355.0,
      price_to_ema21_pct: -0.44,
      ema21_slope: -0.015,
      reasons: ['Price is below EMA21', 'Fast EMA9 stacked below medium EMA21'],
    },
    volatility: {
      state: 'NORMAL',
      dynamics: 'STABLE',
      atr: 2.1,
      atr_relative_ratio: 0.95,
      realized_volatility_pctile: 45.0,
      volatility_quality_score: 90.0,
      reasons: ['Normal balanced volatility regime'],
    },
    momentum: {
      direction: 'SHORT_BIAS',
      strength: 62.0,
      rsi14: 42.1,
      return_5m_pct: -0.15,
      return_15m_pct: -0.42,
      return_30m_pct: -0.55,
      roc: -0.32,
      reasons: ['Downward thrust confirmed'],
    },
    structure: {
      state: 'BEARISH_STRUCTURE',
      quality_score: 75.0,
      recent_swing_high: 1352.0,
      recent_swing_low: 1338.0,
      range_position: 0.32,
      breakout_state: 'WITHIN_RANGE',
      reasons: ['Lower Highs and Lower Lows confirmed'],
    },
    session: {
      state: 'EARLY_SESSION',
      minutes_from_open: 135,
      minutes_to_close: 240,
      session_quality_score: 90.0,
      reasons: ['Prime early session liquidity window'],
    },
    risk: {
      risk_level: 'LOW',
      suggested_risk_distance: 3.2,
      risk_distance_atr_multiple: 1.52,
      estimated_reward_risk_ratio: 1.6,
      risk_quality_score: 85.0,
      warnings: [],
    },
    confidence: {
      score: 72.0,
      agreement_ratio: 1.0,
      conflicting_factors: [],
    },
    explanation: {
      summary: 'TCS at Rs. 1,342.50 presents a SHORT BIAS opportunity (Score: 72/100, Confidence: 72/100) with favorable risk context.',
      evidence: [
        'Trend: Bearish EMA alignment (strength 68)',
        'Structure: Lower Highs and Lower Lows',
        'Momentum: Negative velocity (RSI 42.1)',
      ],
      warnings: [],
      no_trade_reasons: [],
    },
  },
  {
    symbol: 'HDFCBANK',
    timestamp: '2018-06-15 11:30:00',
    price: 945.1,
    direction: 'NEUTRAL',
    opportunity_score: 52.0,
    tradeability_score: 34.0,
    confidence_score: 35.0,
    risk_level: 'HIGH',
    decision: 'NO_TRADE',
    market_condition: 'RANGING',
    trend: {
      direction: 'NEUTRAL',
      state: 'NEUTRAL',
      strength: 22.0,
      ema9: 944.8,
      ema21: 945.2,
      ema50: 945.0,
      price_to_ema21_pct: -0.01,
      ema21_slope: 0.0,
      reasons: ['EMAs intertwined', 'Slope flat'],
    },
    volatility: {
      state: 'LOW',
      dynamics: 'CONTRACTING',
      atr: 0.85,
      atr_relative_ratio: 0.65,
      realized_volatility_pctile: 18.0,
      volatility_quality_score: 70.0,
      reasons: ['Subdued volatility'],
    },
    momentum: {
      direction: 'NEUTRAL',
      strength: 15.0,
      rsi14: 49.5,
      return_5m_pct: 0.02,
      return_15m_pct: -0.04,
      return_30m_pct: 0.01,
      roc: 0.01,
      reasons: ['RSI neutral', 'Flat returns'],
    },
    structure: {
      state: 'RANGE_STRUCTURE',
      quality_score: 50.0,
      recent_swing_high: 948.0,
      recent_swing_low: 942.0,
      range_position: 0.52,
      breakout_state: 'WITHIN_RANGE',
      reasons: ['Price oscillating near midpoint of range (52%)'],
    },
    session: {
      state: 'EARLY_SESSION',
      minutes_from_open: 135,
      minutes_to_close: 240,
      session_quality_score: 90.0,
      reasons: ['Prime early session window'],
    },
    risk: {
      risk_level: 'HIGH',
      suggested_risk_distance: 1.5,
      risk_distance_atr_multiple: 1.76,
      estimated_reward_risk_ratio: 0.75,
      risk_quality_score: 45.0,
      warnings: ['Structural reward/risk is unfavorable (0.75:1)'],
    },
    confidence: {
      score: 35.0,
      agreement_ratio: 0.33,
      conflicting_factors: ['Directional evidence is neutral / undecided'],
    },
    explanation: {
      summary: 'HDFCBANK at Rs. 945.10 is marked NO_TRADE due to conflicting neutral signals and noisy range compression.',
      evidence: ['Volatility is orderly'],
      warnings: ['Price trapped in range center (52%)', 'Low confidence (35/100)'],
      no_trade_reasons: [
        'CONFLICTING_SIGNALS: Directional bias is neutral with conflicting sub-engine votes',
        'RANGE_NO_EDGE: Price trapped in range center without structural momentum',
        'LOW_CONFIDENCE: Confidence score (35.0) is below minimum tradeable threshold (55.0)',
      ],
    },
  },
]

function MarketIntelligenceView() {
  const [overview, setOverview] = useState(null)
  const [opportunities, setOpportunities] = useState(FALLBACK_OPPORTUNITIES)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [symbolDetail, setSymbolDetail] = useState(null)
  const [filterDecision, setFilterDecision] = useState('ALL')
  const [filterBias, setFilterBias] = useState('ALL')
  const [loading, setLoading] = useState(false)

  // Fetch live overview and opportunities
  const loadData = async () => {
    setLoading(true)
    try {
      const [ovData, listData] = await Promise.all([
        fetchIntelligenceOverview().catch(() => null),
        fetchScannedOpportunities().catch(() => null),
      ])

      if (ovData) setOverview(ovData)
      if (listData?.items && listData.items.length > 0) {
        setOpportunities(listData.items)
      }
    } catch {
      // Keep fallbacks
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // When symbol clicked, load detailed intelligence
  const handleSelectSymbol = async (item) => {
    setSelectedSymbol(item.symbol)
    try {
      const detail = await fetchSymbolIntelligence(item.symbol).catch(() => item)
      setSymbolDetail(detail || item)
    } catch {
      setSymbolDetail(item)
    }
  }

  // Filtered list
  const filteredList = useMemo(() => {
    return opportunities.filter((item) => {
      if (filterDecision !== 'ALL' && item.decision !== filterDecision) return false
      if (filterBias !== 'ALL' && item.direction !== filterBias) return false
      return true
    })
  }, [opportunities, filterDecision, filterBias])

  return (
    <div className="intelligence-view">
      {/* Header Area */}
      <div className="intel-header">
        <div className="intel-title-group">
          <h1>
            Market Intelligence Radar
            <span className="intel-badge">Phase 9 Engine</span>
          </h1>
          <p className="intel-subtitle">
            Causal Multi-Engine State Profiler &bull; Opportunity & Tradeability Scoring &bull; Risk Context
          </p>
        </div>

        <div className="intel-header-actions">
          <button
            type="button"
            className="btn-refresh"
            onClick={loadData}
            disabled={loading}
          >
            {loading ? 'Scanning...' : '↻ Refresh Universe'}
          </button>
        </div>
      </div>

      {/* Top Overview Cards Grid */}
      <div className="intel-overview-grid">
        <div className="overview-card">
          <span className="overview-label">Market Condition</span>
          <span className="overview-value">
            {overview?.market_condition || 'TRENDING'}
          </span>
          <span className="overview-sub">Unified Consensus Regime</span>
        </div>

        <div className="overview-card">
          <span className="overview-label">Market Volatility</span>
          <span className="overview-value">
            {overview?.market_volatility || 'NORMAL'}
          </span>
          <span className="overview-sub">Realized ATR Distribution</span>
        </div>

        <div className="overview-card">
          <span className="overview-label">Tradeable Setups</span>
          <span className="overview-value" style={{ color: '#4ade80' }}>
            {overview?.tradeable_count ?? opportunities.filter(o => o.decision === 'TRADEABLE').length}
          </span>
          <span className="overview-sub">Quality & Confidence Verified</span>
        </div>

        <div className="overview-card">
          <span className="overview-label">No-Trade Disqualified</span>
          <span className="overview-value" style={{ color: '#94a3b8' }}>
            {overview?.no_trade_count ?? opportunities.filter(o => o.decision === 'NO_TRADE').length}
          </span>
          <span className="overview-sub">Capital Preservation Active</span>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="intel-filters-bar">
        <div className="filter-group">
          <span className="filter-label">Decision:</span>
          <div className="filter-btn-group">
            {['ALL', 'TRADEABLE', 'CAUTION', 'NO_TRADE'].map((dec) => (
              <button
                key={dec}
                type="button"
                className={`filter-tab ${filterDecision === dec ? 'active' : ''}`}
                onClick={() => setFilterDecision(dec)}
              >
                {dec}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <span className="filter-label">Bias:</span>
          <div className="filter-btn-group">
            {['ALL', 'LONG_BIAS', 'SHORT_BIAS', 'NEUTRAL'].map((bias) => (
              <button
                key={bias}
                type="button"
                className={`filter-tab ${filterBias === bias ? 'active' : ''}`}
                onClick={() => setFilterBias(bias)}
              >
                {bias.replace('_BIAS', '')}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Ranked Table */}
      <div className="intel-table-container">
        <table className="intel-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Symbol</th>
              <th>Price</th>
              <th>Bias</th>
              <th>Opportunity</th>
              <th>Tradeability</th>
              <th>Confidence</th>
              <th>Risk Level</th>
              <th>Decision</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredList.map((item, idx) => {
              const isLong = item.direction === 'LONG_BIAS'
              const isShort = item.direction === 'SHORT_BIAS'
              const biasClass = isLong ? 'badge-long' : isShort ? 'badge-short' : 'badge-neutral'

              const decClass =
                item.decision === 'TRADEABLE'
                  ? 'badge-tradeable'
                  : item.decision === 'CAUTION'
                  ? 'badge-caution'
                  : 'badge-no-trade'

              const riskClass = `risk-${item.risk_level.toLowerCase()}`

              return (
                <tr key={item.symbol} onClick={() => handleSelectSymbol(item)}>
                  <td style={{ color: '#64748b', fontWeight: 600 }}>#{idx + 1}</td>
                  <td className="symbol-name-cell">{item.symbol}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>₹{item.price.toFixed(2)}</td>
                  <td>
                    <span className={`badge-direction ${biasClass}`}>
                      {item.direction.replace('_BIAS', '')}
                    </span>
                  </td>
                  <td>
                    <div className="score-metric-cell">
                      <span className="score-num">{item.opportunity_score.toFixed(0)}</span>
                      <div className="score-bar-bg">
                        <div
                          className="score-bar-fill bar-blue"
                          style={{ width: `${Math.min(100, item.opportunity_score)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="score-metric-cell">
                      <span className="score-num">{item.tradeability_score.toFixed(0)}</span>
                      <div className="score-bar-bg">
                        <div
                          className="score-bar-fill bar-green"
                          style={{ width: `${Math.min(100, item.tradeability_score)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="score-metric-cell">
                      <span className="score-num">{item.confidence_score.toFixed(0)}%</span>
                      <div className="score-bar-bg">
                        <div
                          className="score-bar-fill bar-amber"
                          style={{ width: `${Math.min(100, item.confidence_score)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`badge-risk ${riskClass}`}>{item.risk_level}</span>
                  </td>
                  <td>
                    <span className={`badge-decision ${decClass}`}>{item.decision}</span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn-refresh"
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleSelectSymbol(item)
                      }}
                    >
                      Inspect →
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Selected Symbol Detail Drawer / Modal */}
      {selectedSymbol && symbolDetail && (
        <div className="intel-modal-backdrop" onClick={() => setSelectedSymbol(null)}>
          <div className="intel-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h2 style={{ margin: 0, fontSize: '1.3rem', color: '#fff' }}>
                    {symbolDetail.symbol}
                  </h2>
                  <span
                    className={`badge-direction ${
                      symbolDetail.direction === 'LONG_BIAS'
                        ? 'badge-long'
                        : symbolDetail.direction === 'SHORT_BIAS'
                        ? 'badge-short'
                        : 'badge-neutral'
                    }`}
                  >
                    {symbolDetail.direction.replace('_BIAS', '')}
                  </span>
                  <span
                    className={`badge-decision ${
                      symbolDetail.decision === 'TRADEABLE'
                        ? 'badge-tradeable'
                        : symbolDetail.decision === 'CAUTION'
                        ? 'badge-caution'
                        : 'badge-no-trade'
                    }`}
                  >
                    {symbolDetail.decision}
                  </span>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Price: ₹{symbolDetail.price.toFixed(2)} &bull; Timestamp: {symbolDetail.timestamp}
                </div>
              </div>

              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setSelectedSymbol(null)}
              >
                ✕
              </button>
            </div>

            <div className="drawer-body">
              {/* Executive Summary */}
              <div className="intel-summary-banner">
                {symbolDetail.explanation.summary}
              </div>

              {/* Disqualification Reasons if NO_TRADE */}
              {symbolDetail.explanation.no_trade_reasons.length > 0 && (
                <div className="fact-block" style={{ borderColor: 'rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.05)' }}>
                  <div className="fact-title title-no-trade">
                    ⚠️ Disqualification / NO_TRADE Enforcement
                  </div>
                  <ul className="fact-list">
                    {symbolDetail.explanation.no_trade_reasons.map((r, i) => (
                      <li key={i} className="fact-item" style={{ color: '#fca5a5' }}>
                        &bull; {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Positive Evidence Block */}
              <div className="fact-block">
                <div className="fact-title title-evidence">
                  ✓ Supportive Structural Evidence
                </div>
                <ul className="fact-list">
                  {symbolDetail.explanation.evidence.map((ev, i) => (
                    <li key={i} className="fact-item">
                      <span style={{ color: '#4ade80' }}>+</span> {ev}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Active Warnings Block */}
              {symbolDetail.explanation.warnings.length > 0 && (
                <div className="fact-block">
                  <div className="fact-title title-warnings">
                    ⚡ Active Contextual Warnings & Risks
                  </div>
                  <ul className="fact-list">
                    {symbolDetail.explanation.warnings.map((w, i) => (
                      <li key={i} className="fact-item">
                        <span style={{ color: '#fbbf24' }}>-</span> {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Component Engines Detailed Grid */}
              <div className="engines-breakdown-grid">
                {/* Trend Card */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span>Trend Engine</span>
                    <span style={{ color: '#38bdf8' }}>{symbolDetail.trend.strength.toFixed(0)}/100</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">State</span>
                    <span className="engine-metric-val">{symbolDetail.trend.state}</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">EMA Stack</span>
                    <span className="engine-metric-val">
                      9: {symbolDetail.trend.ema9.toFixed(1)} | 21: {symbolDetail.trend.ema21.toFixed(1)}
                    </span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">EMA21 Trajectory</span>
                    <span className="engine-metric-val">{symbolDetail.trend.ema21_slope.toFixed(3)}%/bar</span>
                  </div>
                </div>

                {/* Volatility Card */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span>Volatility Engine</span>
                    <span style={{ color: '#38bdf8' }}>{symbolDetail.volatility.volatility_quality_score.toFixed(0)}/100</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Regime</span>
                    <span className="engine-metric-val">{symbolDetail.volatility.state}</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">ATR (14)</span>
                    <span className="engine-metric-val">₹{symbolDetail.volatility.atr.toFixed(2)} ({symbolDetail.volatility.atr_relative_ratio}x)</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Dynamics</span>
                    <span className="engine-metric-val">{symbolDetail.volatility.dynamics}</span>
                  </div>
                </div>

                {/* Structure Card */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span>Market Structure</span>
                    <span style={{ color: '#38bdf8' }}>{symbolDetail.structure.quality_score.toFixed(0)}/100</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Progression</span>
                    <span className="engine-metric-val">{symbolDetail.structure.state.replace('_', ' ')}</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Range Pos</span>
                    <span className="engine-metric-val">{(symbolDetail.structure.range_position * 100).toFixed(0)}%</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">20-bar Range</span>
                    <span className="engine-metric-val">
                      ₹{symbolDetail.structure.recent_swing_low.toFixed(1)} – ₹{symbolDetail.structure.recent_swing_high.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Risk Context Card */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span>Risk Context</span>
                    <span className={`badge-risk risk-${symbolDetail.risk.risk_level.toLowerCase()}`}>
                      {symbolDetail.risk.risk_level}
                    </span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Suggested Risk Dist</span>
                    <span className="engine-metric-val">₹{symbolDetail.risk.suggested_risk_distance.toFixed(2)} ({symbolDetail.risk.risk_distance_atr_multiple} ATR)</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Reward/Risk Ratio</span>
                    <span className="engine-metric-val">{symbolDetail.risk.estimated_reward_risk_ratio.toFixed(2)}:1</span>
                  </div>
                  <div className="engine-metric-row">
                    <span className="engine-metric-label">Session Window</span>
                    <span className="engine-metric-val">{symbolDetail.session.state.replace('_', ' ')}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MarketIntelligenceView
