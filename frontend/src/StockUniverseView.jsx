import React, { useState, useEffect, useCallback, useMemo } from 'react'
import './StockUniverseView.css'
import {
  fetchUniverseStocks,
  addUniverseStock,
  fetchStockQualifications,
  fetchStockQualification,
  updateStockQualification,
  fetchUniverseStockReadiness,
} from './api'
import { LoadingState, ErrorState, EmptyState } from './StateViews'

// Qualification status badge formatting
const STATUS_CONFIG = {
  APPROVED: {
    label: 'APPROVED',
    subtitle: 'Qualification criteria met',
    badgeClass: 'status-approved',
  },
  IN_PROGRESS: {
    label: 'IN PROGRESS',
    subtitle: 'Forward testing in progress',
    badgeClass: 'status-in-progress',
  },
  INSUFFICIENT_DATA: {
    label: 'INSUFFICIENT DATA',
    subtitle: 'Incomplete evidence sample',
    badgeClass: 'status-insufficient',
  },
  REJECTED: {
    label: 'REJECTED',
    subtitle: 'Did not meet criteria',
    badgeClass: 'status-rejected',
  },
  NOT_TESTED: {
    label: 'NOT TESTED',
    subtitle: 'No test record',
    badgeClass: 'status-not-tested',
  },
}

const CATEGORIES = [
  { id: 'ALL', label: 'All Stocks' },
  { id: 'NIFTY_50', label: 'NIFTY 50' },
  { id: 'NIFTY_NEXT_50', label: 'NIFTY Next 50' },
  { id: 'CUSTOM', label: 'Custom' },
]

export default function StockUniverseView() {
  // Navigation / Filter state
  const [activeCategory, setActiveCategory] = useState('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  // Stocks list state
  const [stocks, setStocks] = useState([])
  const [stocksLoading, setStocksLoading] = useState(true)
  const [stocksError, setStocksError] = useState(null)
  const [selectedStock, setSelectedStock] = useState(null)

  // Qualification records state for selected stock
  const [qualifications, setQualifications] = useState([])
  const [selectedStrategyId, setSelectedStrategyId] = useState('SignalForge_V1')
  const [activeQualRecord, setActiveQualRecord] = useState(null)
  const [qualLoading, setQualLoading] = useState(false)
  const [qualError, setQualError] = useState(null)

  // Readiness assessment state
  const [readinessRecord, setReadinessRecord] = useState(null)

  // Add stock modal / drawer state
  const [showAddModal, setShowAddModal] = useState(false)
  const [addSymbol, setAddSymbol] = useState('')
  const [addName, setAddName] = useState('')
  const [addExchange, setAddExchange] = useState('NSE')
  const [addCategory, setAddCategory] = useState('CUSTOM')
  const [addError, setAddError] = useState(null)
  const [addSuccess, setAddSuccess] = useState(null)
  const [isSubmittingStock, setIsSubmittingStock] = useState(false)

  // Update qualification form state
  const [showUpdateDrawer, setShowUpdateDrawer] = useState(false)
  const [updateStrategyId, setUpdateStrategyId] = useState('SignalForge_V1')
  const [updateStrategyVersion, setUpdateStrategyVersion] = useState('1.0')
  const [updateHistoricalStatus, setUpdateHistoricalStatus] = useState('READY')
  const [updateBacktestStatus, setUpdateBacktestStatus] = useState('PASSED')
  const [updateBacktestProfit, setUpdateBacktestProfit] = useState('150.0')
  const [updateOosStatus, setUpdateOosStatus] = useState('PASSED')
  const [updateForwardStatus, setUpdateForwardStatus] = useState('PASSED')
  const [updateTradeCount, setUpdateTradeCount] = useState('30')
  const [updateTargetQualStatus, setUpdateTargetQualStatus] = useState('APPROVED')
  const [updateReason, setUpdateReason] = useState('')
  const [updateEvidenceRef, setUpdateEvidenceRef] = useState('')
  const [updateError, setUpdateError] = useState(null)
  const [updateSuccess, setUpdateSuccess] = useState(null)
  const [isUpdatingQual, setIsUpdatingQual] = useState(false)

  // Load stocks
  const loadStocks = useCallback(async () => {
    setStocksLoading(true)
    setStocksError(null)

    try {
      const data = await fetchUniverseStocks(activeCategory, searchQuery)
      setStocks(Array.isArray(data) ? data : [])
    } catch (err) {
      setStocksError(err instanceof Error ? err.message : 'Failed to load stock universe')
      setStocks([])
    } finally {
      setStocksLoading(false)
    }
  }, [activeCategory, searchQuery])

  useEffect(() => {
    loadStocks()
  }, [loadStocks])

  // Automatically select first stock when stocks update if none selected
  useEffect(() => {
    if (stocks.length > 0) {
      if (!selectedStock || !stocks.some((s) => s.symbol === selectedStock.symbol)) {
        setSelectedStock(stocks[0])
      }
    } else {
      setSelectedStock(null)
      setQualifications([])
      setActiveQualRecord(null)
      setReadinessRecord(null)
    }
  }, [stocks, selectedStock])

  // Load qualifications when selected stock changes
  const loadQualifications = useCallback(async (symbol) => {
    if (!symbol) return

    setQualLoading(true)
    setQualError(null)

    try {
      // 1. Fetch all qualifications for this stock
      const allQuals = await fetchStockQualifications(symbol)
      setQualifications(Array.isArray(allQuals) ? allQuals : [])

      // 2. Fetch or fallback to the specific active strategy qualification
      let record = null
      if (Array.isArray(allQuals) && allQuals.length > 0) {
        const found = allQuals.find((q) => q.strategy_id === selectedStrategyId)
        if (found) {
          record = found
        }
      }

      if (!record) {
        // Backend returns default NOT_TESTED record if strategy record doesn't exist yet
        record = await fetchStockQualification(symbol, selectedStrategyId)
      }

      setActiveQualRecord(record)

      // 3. Fetch read-only readiness assessment
      try {
        const rData = await fetchUniverseStockReadiness(symbol, selectedStrategyId)
        setReadinessRecord(rData)
      } catch (rErr) {
        setReadinessRecord(null)
      }
    } catch (err) {
      setQualError(err instanceof Error ? err.message : 'Failed to load qualification record')
      setActiveQualRecord(null)
      setReadinessRecord(null)
    } finally {
      setQualLoading(false)
    }
  }, [selectedStrategyId])

  useEffect(() => {
    if (selectedStock?.symbol) {
      loadQualifications(selectedStock.symbol)
    }
  }, [selectedStock, loadQualifications])

  // Handle Add Stock submission
  const handleAddStockSubmit = async (e) => {
    e.preventDefault()
    setAddError(null)
    setAddSuccess(null)

    const symbolClean = addSymbol.trim().toUpperCase()
    const exchangeClean = addExchange.trim().toUpperCase()

    if (!symbolClean) {
      setAddError('Stock symbol is required.')
      return
    }

    if (!exchangeClean) {
      setAddError('Exchange is required.')
      return
    }

    setIsSubmittingStock(true)

    try {
      const newStock = await addUniverseStock({
        symbol: symbolClean,
        name: addName.trim() || null,
        exchange: exchangeClean,
        category: addCategory,
      })

      setAddSuccess(`Stock ${newStock.symbol} (${newStock.exchange}) successfully registered.`)
      setAddSymbol('')
      setAddName('')
      setAddExchange('NSE')
      setAddCategory('CUSTOM')

      // Refresh stock universe list and select newly added stock
      await loadStocks()
      setSelectedStock(newStock)

      setTimeout(() => {
        setShowAddModal(false)
        setAddSuccess(null)
      }, 1200)
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to register stock')
    } finally {
      setIsSubmittingStock(false)
    }
  }

  // Populate update form when opening drawer
  const handleOpenUpdateForm = () => {
    setUpdateError(null)
    setUpdateSuccess(null)
    if (activeQualRecord) {
      setUpdateStrategyId(activeQualRecord.strategy_id || 'SignalForge_V1')
      setUpdateStrategyVersion(activeQualRecord.strategy_version || '1.0')
      setUpdateHistoricalStatus(activeQualRecord.historical_data_status || 'READY')
      setUpdateBacktestStatus(activeQualRecord.backtest_status || 'PASSED')
      setUpdateBacktestProfit(
        activeQualRecord.backtest_net_profit != null ? String(activeQualRecord.backtest_net_profit) : ''
      )
      setUpdateOosStatus(activeQualRecord.oos_validation_status || 'PASSED')
      setUpdateForwardStatus(activeQualRecord.forward_paper_test_status || 'PASSED')
      setUpdateTradeCount(String(activeQualRecord.completed_trade_count || 0))
      setUpdateTargetQualStatus(activeQualRecord.qualification_status || 'NOT_TESTED')
      setUpdateReason(activeQualRecord.status_reason || '')
      setUpdateEvidenceRef(activeQualRecord.evidence_reference || '')
    }
    setShowUpdateDrawer(true)
  }

  // Handle Qualification Update submission
  const handleUpdateQualSubmit = async (e) => {
    e.preventDefault()
    setUpdateError(null)
    setUpdateSuccess(null)

    if (!selectedStock?.symbol) {
      setUpdateError('No stock selected for qualification update.')
      return
    }

    const tradeCountInt = parseInt(updateTradeCount, 10)
    if (Number.isNaN(tradeCountInt) || tradeCountInt < 0) {
      setUpdateError('Completed trade count must be a non-negative integer.')
      return
    }

    let profitVal = null
    if (updateBacktestProfit !== '' && updateBacktestProfit != null) {
      const parsedProfit = parseFloat(updateBacktestProfit)
      if (Number.isNaN(parsedProfit) || !Number.isFinite(parsedProfit)) {
        setUpdateError('Backtest net profit must be a valid finite number.')
        return
      }
      profitVal = parsedProfit
    }

    setIsUpdatingQual(true)

    try {
      const updated = await updateStockQualification(
        selectedStock.symbol,
        updateStrategyId.trim() || 'SignalForge_V1',
        {
          strategy_version: updateStrategyVersion.trim() || '1.0',
          historical_data_status: updateHistoricalStatus,
          backtest_status: updateBacktestStatus,
          backtest_net_profit: profitVal,
          oos_validation_status: updateOosStatus,
          forward_paper_test_status: updateForwardStatus,
          completed_trade_count: tradeCountInt,
          qualification_status: updateTargetQualStatus,
          status_reason: updateReason.trim() || null,
          evidence_reference: updateEvidenceRef.trim() || null,
        }
      )

      setUpdateSuccess(`Qualification assertion recorded: ${updated.qualification_status}`)
      setActiveQualRecord(updated)
      await loadQualifications(selectedStock.symbol)

      setTimeout(() => {
        setShowUpdateDrawer(false)
        setUpdateSuccess(null)
      }, 1400)
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : 'Failed to update qualification record')
    } finally {
      setIsUpdatingQual(false)
    }
  }

  // Format dates safely
  const formatDate = (isoString) => {
    if (!isoString) return '—'
    const date = new Date(isoString)
    if (Number.isNaN(date.getTime())) return String(isoString)
    return new Intl.DateTimeFormat('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Asia/Kolkata',
    }).format(date)
  }

  // Format currency
  const formatCurrency = (val) => {
    if (val == null || typeof val !== 'number' || Number.isNaN(val)) return '—'
    return `₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  // Progress metrics for forward trades threshold
  const currentTrades = activeQualRecord?.completed_trade_count || 0
  const initialMet = currentTrades >= 30
  const preferredMet = currentTrades >= 50
  const progressPercent = Math.min(100, Math.round((currentTrades / 50) * 100))

  const activeQualConfig =
    STATUS_CONFIG[activeQualRecord?.qualification_status] || STATUS_CONFIG.NOT_TESTED

  return (
    <div className="stock-universe-view">
      {/* Header & Governance Notice */}
      <header className="universe-header">
        <div className="universe-header-title">
          <div className="universe-title-row">
            <h1>Stock Universe & Qualification Governance</h1>
            <span className="universe-badge">Phase 24E.3 Registry</span>
          </div>
          <p className="universe-subtitle">
            Manage registered instruments and verify forward-paper trade qualification criteria.
          </p>
        </div>

        <div className="universe-header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadStocks}
            disabled={stocksLoading}
            title="Refresh stock list"
          >
            <span className="btn-icon">↻</span> Refresh
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setAddError(null)
              setAddSuccess(null)
              setShowAddModal(true)
            }}
          >
            <span className="btn-icon">+</span> Register Stock
          </button>
        </div>
      </header>

      {/* Governance & Disclaimer Notice */}
      <div className="governance-disclaimer" role="note" aria-label="Governance notice">
        <div className="disclaimer-icon" aria-hidden="true">🛡️</div>
        <div className="disclaimer-content">
          <strong>Qualification Governance Notice:</strong>
          <span>
            An <code>APPROVED</code> qualification status confirms that recorded multi-stage evidence
            satisfies the configured gate thresholds (minimum 30 completed forward trades, 50 preferred sample).
            <strong> Approval does not guarantee future profitability, eliminate market risk, or authorize live broker execution.</strong>
          </span>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="universe-layout">
        {/* Left Column: Stock Universe Registry */}
        <section className="universe-registry-panel panel" aria-label="Stock Universe Registry">
          <div className="panel-header registry-header">
            <div className="search-box">
              <span className="search-icon" aria-hidden="true">🔍</span>
              <input
                type="text"
                placeholder="Search symbol or company..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search registered stocks"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="search-clear-btn"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search query"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="category-tabs" role="tablist" aria-label="Stock category filter">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  role="tab"
                  className={`category-tab ${activeCategory === cat.id ? 'active' : ''}`}
                  aria-selected={activeCategory === cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div className="registry-body">
            {stocksLoading ? (
              <LoadingState
                title="Loading Stock Universe..."
                description="Querying persistent universe registry."
                compact
              />
            ) : stocksError ? (
              <ErrorState
                title="Failed to Load Stock Universe"
                message={stocksError}
                onRetry={loadStocks}
                retryLabel="Retry Registry Query"
                compact
              />
            ) : stocks.length === 0 ? (
              <EmptyState
                title="No Stocks Registered"
                description={
                  activeCategory === 'ALL'
                    ? 'No stocks are currently registered in the SignalForge universe. Use "Register Stock" to add one.'
                    : `No registered stocks found in category "${activeCategory}". Use "Register Stock" or switch filter tabs.`
                }
                action={
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setAddCategory(activeCategory !== 'ALL' ? activeCategory : 'CUSTOM')
                      setShowAddModal(true)
                    }}
                  >
                    + Register {activeCategory !== 'ALL' ? activeCategory : 'New'} Stock
                  </button>
                }
                compact
              />
            ) : (
              <div className="stock-list" role="listbox" aria-label="Registered stocks">
                {stocks.map((stock) => {
                  const isSelected = selectedStock?.symbol === stock.symbol
                  return (
                    <div
                      key={`${stock.exchange}:${stock.symbol}`}
                      role="option"
                      aria-selected={isSelected}
                      tabIndex={0}
                      className={`stock-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => setSelectedStock(stock)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          setSelectedStock(stock)
                        }
                      }}
                    >
                      <div className="stock-item-left">
                        <div className="stock-symbol-row">
                          <span className="stock-symbol">{stock.symbol}</span>
                          <span className="stock-exchange">{stock.exchange}</span>
                          <span className={`stock-category-pill category-${stock.category.toLowerCase()}`}>
                            {stock.category.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="stock-name">
                          {stock.name || <span className="muted-dash">—</span>}
                        </div>
                      </div>

                      <div className="stock-item-right">
                        <span
                          className={`quality-status-badge quality-${(stock.data_quality_status || 'UNKNOWN').toLowerCase()}`}
                          title={`Data quality: ${stock.data_quality_status}`}
                        >
                          {stock.data_quality_status}
                        </span>
                        <span className="stock-chevron" aria-hidden="true">→</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="registry-footer">
            <span className="registry-count-label">
              Total registered: <strong>{stocks.length}</strong>
            </span>
          </div>
        </section>

        {/* Right Column: Strategy Qualification Details & Management */}
        <section className="universe-qual-panel panel" aria-label="Strategy Qualification Governance">
          {selectedStock ? (
            <div className="qual-content">
              {/* Selected Stock Overview Banner */}
              <div className="stock-header-card">
                <div className="stock-meta-left">
                  <div className="stock-title-badge">
                    <h2>{selectedStock.symbol}</h2>
                    <span className="stock-exchange-pill">{selectedStock.exchange}</span>
                    <span className="stock-cat-pill">{selectedStock.category}</span>
                  </div>
                  <div className="stock-company-name">
                    {selectedStock.name || 'Company name unassigned'}
                  </div>
                </div>

                <div className="stock-meta-right">
                  <div className="meta-timestamp">
                    <span className="meta-label">Added to Universe:</span>
                    <span className="meta-val">{formatDate(selectedStock.created_at)}</span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handleOpenUpdateForm}
                  >
                    ✎ Record Qualification Claim
                  </button>
                </div>
              </div>

              {/* Strategy selector tab if multiple qualifications exist */}
              <div className="strategy-selector-bar">
                <span className="selector-label">Strategy Under Governance:</span>
                <span className="strategy-active-tag">
                  <strong>{selectedStrategyId}</strong> (v{activeQualRecord?.strategy_version || '1.0'})
                </span>
              </div>

              {qualLoading ? (
                <LoadingState
                  title="Loading Qualification Governance Record..."
                  description={`Fetching multi-stage validation evidence for ${selectedStock.symbol}...`}
                />
              ) : qualError ? (
                <ErrorState
                  title="Qualification Fetch Failed"
                  message={qualError}
                  onRetry={() => loadQualifications(selectedStock.symbol)}
                />
              ) : activeQualRecord ? (
                <div className="qual-card">
                  {/* Gate Status Card */}
                  <div className="gate-status-section">
                    <div className="gate-status-header">
                      <div className="status-badge-container">
                        <span className={`qual-status-badge ${activeQualConfig.badgeClass}`}>
                          {activeQualConfig.label}
                        </span>
                        <span className="qual-status-subtitle">{activeQualConfig.subtitle}</span>
                      </div>

                      <div className="sample-threshold-summary">
                        <span className="sample-count-pill">
                          <strong>{currentTrades}</strong> Forward Trades
                        </span>
                      </div>
                    </div>

                    {/* Trade Count Threshold Meter */}
                    <div className="threshold-meter-card">
                      <div className="meter-label-row">
                        <span className="meter-title">Forward Paper Trade Sample Progress</span>
                        <span className="meter-values">
                          {currentTrades} / 30 Min (50 Preferred)
                        </span>
                      </div>

                      <div className="meter-bar-track" aria-hidden="true">
                        <div
                          className={`meter-bar-fill ${initialMet ? 'fill-passed' : 'fill-pending'}`}
                          style={{ width: `${progressPercent}%` }}
                        />
                        <div className="meter-marker marker-30" title="Minimum 30 trades" />
                        <div className="meter-marker marker-50" title="Preferred 50 trades" />
                      </div>

                      <div className="meter-milestones">
                        <span className={`milestone ${initialMet ? 'milestone-met' : 'milestone-unmet'}`}>
                          {initialMet ? '✓' : '○'} Minimum Evaluation Threshold (30)
                        </span>
                        <span className={`milestone ${preferredMet ? 'milestone-met' : 'milestone-unmet'}`}>
                          {preferredMet ? '✓' : '○'} Preferred Strong Sample (50)
                        </span>
                      </div>

                      <p className="threshold-disclaimer">
                        <strong>Important:</strong> Achieving ≥ 30 completed forward paper trades is a prerequisite,
                        not standalone proof of profitability. All historical and forward evidence checks must pass.
                      </p>
                    </div>
                  </div>

                  {/* Multi-Stage Validation Pipeline Grid */}
                  <div className="evidence-pipeline-section">
                    <h3 className="section-title">Validation Evidence Pipeline</h3>
                    <div className="stages-grid">
                      {/* 1. Historical Data */}
                      <div className="stage-card">
                        <div className="stage-header">
                          <span className="stage-num">Stage 1</span>
                          <span className="stage-name">Historical Data</span>
                        </div>
                        <div className="stage-val">
                          <span className={`status-dot dot-${(activeQualRecord.historical_data_status || 'UNKNOWN').toLowerCase()}`} />
                          <strong>{activeQualRecord.historical_data_status || 'UNKNOWN'}</strong>
                        </div>
                        <span className="stage-desc">Readiness for causal replay</span>
                      </div>

                      {/* 2. Backtest Status */}
                      <div className="stage-card">
                        <div className="stage-header">
                          <span className="stage-num">Stage 2</span>
                          <span className="stage-name">Historical Backtest</span>
                        </div>
                        <div className="stage-val">
                          <span className={`status-dot dot-${(activeQualRecord.backtest_status || 'UNKNOWN').toLowerCase()}`} />
                          <strong>{activeQualRecord.backtest_status || 'UNKNOWN'}</strong>
                        </div>
                        <span className="stage-desc">
                          Net Profit: <strong>{formatCurrency(activeQualRecord.backtest_net_profit)}</strong>
                        </span>
                      </div>

                      {/* 3. OOS Validation */}
                      <div className="stage-card">
                        <div className="stage-header">
                          <span className="stage-num">Stage 3</span>
                          <span className="stage-name">Out-of-Sample</span>
                        </div>
                        <div className="stage-val">
                          <span className={`status-dot dot-${(activeQualRecord.oos_validation_status || 'UNKNOWN').toLowerCase()}`} />
                          <strong>{activeQualRecord.oos_validation_status || 'UNKNOWN'}</strong>
                        </div>
                        <span className="stage-desc">Post-training unseen verification</span>
                      </div>

                      {/* 4. Forward Paper Testing */}
                      <div className="stage-card">
                        <div className="stage-header">
                          <span className="stage-num">Stage 4</span>
                          <span className="stage-name">Forward Paper Testing</span>
                        </div>
                        <div className="stage-val">
                          <span className={`status-dot dot-${(activeQualRecord.forward_paper_test_status || 'UNKNOWN').toLowerCase()}`} />
                          <strong>{activeQualRecord.forward_paper_test_status || 'UNKNOWN'}</strong>
                        </div>
                        <span className="stage-desc">
                          Sample size: <strong>{activeQualRecord.completed_trade_count} trades</strong>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Readiness Assessment & Data Quality */}
                  {readinessRecord && (
                    <div className="readiness-section" role="region" aria-label="Strategy Readiness Assessment">
                      <div className="readiness-section-header">
                        <h3 className="section-title">Readiness Assessment & Data Audit</h3>
                        <span className={`readiness-state-pill pill-${(readinessRecord.readiness_state || '').toLowerCase()}`}>
                          {readinessRecord.readiness_state}
                        </span>
                      </div>

                      <div className="next-step-card">
                        <span className="next-step-label">NEXT REQUIRED EVALUATION STEP</span>
                        <p className="next-step-text">{readinessRecord.next_required_step}</p>
                      </div>

                      <div className="readiness-grid">
                        <div className="readiness-item">
                          <span className="readiness-lbl">Local 1m Data:</span>
                          <span className="readiness-v">
                            {readinessRecord.data_quality.has_local_data ? '✓ Present' : '✗ Missing'}
                          </span>
                        </div>
                        <div className="readiness-item">
                          <span className="readiness-lbl">Candle Count:</span>
                          <span className="readiness-v">
                            {readinessRecord.data_quality.total_candles.toLocaleString()}
                            {readinessRecord.data_quality.total_candles < 500 && ' (< 500)'}
                          </span>
                        </div>
                        <div className="readiness-item">
                          <span className="readiness-lbl">Data Quality Status:</span>
                          <span className="readiness-v">
                            {readinessRecord.data_quality.data_quality_status}
                          </span>
                        </div>
                        <div className="readiness-item">
                          <span className="readiness-lbl">Exchange Validity:</span>
                          <span className="readiness-v">
                            {readinessRecord.exchange_valid ? `✓ Valid (${readinessRecord.exchange})` : `✗ Invalid (${readinessRecord.exchange})`}
                          </span>
                        </div>
                      </div>

                      {readinessRecord.missing_evidence && readinessRecord.missing_evidence.length > 0 && (
                        <div className="missing-evidence-wrap">
                          <span className="missing-evidence-label">Pending / Missing Evidence:</span>
                          <ul className="missing-evidence-items">
                            {readinessRecord.missing_evidence.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Audit Trail & Evidence Metadata */}
                  <div className="audit-trail-section">
                    <h3 className="section-title">Audit Reference & Recorded Reason</h3>
                    <div className="audit-grid">
                      <div className="audit-item">
                        <span className="audit-label">Status Reason:</span>
                        <p className="audit-val reason-text">
                          {activeQualRecord.status_reason || 'No specific rationale recorded.'}
                        </p>
                      </div>

                      <div className="audit-item">
                        <span className="audit-label">Evidence Reference:</span>
                        <p className="audit-val">
                          {activeQualRecord.evidence_reference ? (
                            <code>{activeQualRecord.evidence_reference}</code>
                          ) : (
                            <span className="muted-dash">No reference attached</span>
                          )}
                        </p>
                      </div>

                      <div className="audit-item">
                        <span className="audit-label">Last Audited / Updated:</span>
                        <p className="audit-val">
                          {formatDate(activeQualRecord.updated_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No Qualification Record"
                  description="No qualification status has been recorded for this stock and strategy."
                  action={
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleOpenUpdateForm}
                    >
                      Record Initial Assessment
                    </button>
                  }
                />
              )}
            </div>
          ) : (
            <div className="no-selection-wrap">
              <EmptyState
                title="Select a Stock"
                description="Choose an instrument from the stock universe registry on the left to review its qualification gates and validation audit trail."
              />
            </div>
          )}
        </section>
      </div>

      {/* MODAL: Register Custom Stock */}
      {showAddModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="add-stock-modal-title">
          <div className="modal-box">
            <div className="modal-header">
              <h2 id="add-stock-modal-title">Register Stock in Universe</h2>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowAddModal(false)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddStockSubmit} className="modal-form">
              {addError && (
                <div className="form-alert alert-error" role="alert">
                  ⚠️ {addError}
                </div>
              )}
              {addSuccess && (
                <div className="form-alert alert-success" role="status">
                  ✓ {addSuccess}
                </div>
              )}

              <div className="form-group">
                <label htmlFor="reg-symbol">Symbol *</label>
                <input
                  id="reg-symbol"
                  type="text"
                  required
                  placeholder="e.g. TCS, INFY, RELIANCE"
                  value={addSymbol}
                  onChange={(e) => setAddSymbol(e.target.value)}
                  disabled={isSubmittingStock}
                />
                <span className="form-hint">Unique ticker symbol (case-insensitive)</span>
              </div>

              <div className="form-group">
                <label htmlFor="reg-name">Company Name (Optional)</label>
                <input
                  id="reg-name"
                  type="text"
                  placeholder="e.g. Tata Consultancy Services Ltd."
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  disabled={isSubmittingStock}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="reg-exchange">Exchange *</label>
                  <input
                    id="reg-exchange"
                    type="text"
                    required
                    placeholder="NSE"
                    value={addExchange}
                    onChange={(e) => setAddExchange(e.target.value)}
                    disabled={isSubmittingStock}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="reg-category">Category *</label>
                  <select
                    id="reg-category"
                    value={addCategory}
                    onChange={(e) => setAddCategory(e.target.value)}
                    disabled={isSubmittingStock}
                  >
                    <option value="CUSTOM">CUSTOM</option>
                    <option value="NIFTY_50">NIFTY_50</option>
                    <option value="NIFTY_NEXT_50">NIFTY_NEXT_50</option>
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddModal(false)}
                  disabled={isSubmittingStock}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmittingStock}
                >
                  {isSubmittingStock ? 'Registering...' : 'Register Stock'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER / MODAL: Update Qualification (Recorded Assertions) */}
      {showUpdateDrawer && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="update-qual-title">
          <div className="modal-box modal-box-wide">
            <div className="modal-header">
              <div>
                <h2 id="update-qual-title">
                  Record Qualification Assessment — {selectedStock?.symbol}
                </h2>
                <p className="modal-subtitle">
                  Controlled qualification gate record. Submissions are strictly verified against governance rules.
                </p>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowUpdateDrawer(false)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateQualSubmit} className="modal-form">
              {updateError && (
                <div className="form-alert alert-error" role="alert">
                  <strong>Validation Failure:</strong> {updateError}
                </div>
              )}
              {updateSuccess && (
                <div className="form-alert alert-success" role="status">
                  ✓ {updateSuccess}
                </div>
              )}

              <div className="form-notice">
                <span>
                  <strong>Recorded Claim Notice:</strong> Submitting this form records qualification assertions
                  subject to backend hardening (trade count &gt;= 30 for approval, consistent readiness, finite positive profit).
                  It does NOT enable live trading execution.
                </span>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="up-strat-id">Strategy ID *</label>
                  <input
                    id="up-strat-id"
                    type="text"
                    required
                    value={updateStrategyId}
                    onChange={(e) => setUpdateStrategyId(e.target.value)}
                    disabled={isUpdatingQual}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="up-strat-ver">Strategy Version *</label>
                  <input
                    id="up-strat-ver"
                    type="text"
                    required
                    value={updateStrategyVersion}
                    onChange={(e) => setUpdateStrategyVersion(e.target.value)}
                    disabled={isUpdatingQual}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="up-hist-status">Historical Data Status *</label>
                  <select
                    id="up-hist-status"
                    value={updateHistoricalStatus}
                    onChange={(e) => setUpdateHistoricalStatus(e.target.value)}
                    disabled={isUpdatingQual}
                  >
                    <option value="READY">READY</option>
                    <option value="INCOMPLETE">INCOMPLETE</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="up-bt-status">Backtest Status *</label>
                  <select
                    id="up-bt-status"
                    value={updateBacktestStatus}
                    onChange={(e) => setUpdateBacktestStatus(e.target.value)}
                    disabled={isUpdatingQual}
                  >
                    <option value="PASSED">PASSED</option>
                    <option value="FAILED">FAILED</option>
                    <option value="NOT_TESTED">NOT_TESTED</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="up-bt-profit">Backtest Net Profit (₹)</label>
                  <input
                    id="up-bt-profit"
                    type="number"
                    step="any"
                    placeholder="e.g. 250.5"
                    value={updateBacktestProfit}
                    onChange={(e) => setUpdateBacktestProfit(e.target.value)}
                    disabled={isUpdatingQual}
                  />
                  <span className="form-hint">Required &gt; 0 when backtest PASSED</span>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="up-oos-status">Out-of-Sample (OOS) Status *</label>
                  <select
                    id="up-oos-status"
                    value={updateOosStatus}
                    onChange={(e) => setUpdateOosStatus(e.target.value)}
                    disabled={isUpdatingQual}
                  >
                    <option value="PASSED">PASSED</option>
                    <option value="FAILED">FAILED</option>
                    <option value="NOT_TESTED">NOT_TESTED</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="up-fwd-status">Forward Paper Test Status *</label>
                  <select
                    id="up-fwd-status"
                    value={updateForwardStatus}
                    onChange={(e) => setUpdateForwardStatus(e.target.value)}
                    disabled={isUpdatingQual}
                  >
                    <option value="PASSED">PASSED</option>
                    <option value="FAILED">FAILED</option>
                    <option value="NOT_TESTED">NOT_TESTED</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="up-trade-count">Completed Forward Trades *</label>
                  <input
                    id="up-trade-count"
                    type="number"
                    min="0"
                    required
                    value={updateTradeCount}
                    onChange={(e) => setUpdateTradeCount(e.target.value)}
                    disabled={isUpdatingQual}
                  />
                  <span className="form-hint">≥30 required for APPROVED status</span>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="up-qual-status">Qualification Status *</label>
                  <select
                    id="up-qual-status"
                    value={updateTargetQualStatus}
                    onChange={(e) => setUpdateTargetQualStatus(e.target.value)}
                    disabled={isUpdatingQual}
                  >
                    <option value="APPROVED">APPROVED (Gates must pass)</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="INSUFFICIENT_DATA">INSUFFICIENT_DATA</option>
                    <option value="REJECTED">REJECTED</option>
                    <option value="NOT_TESTED">NOT_TESTED</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="up-evid-ref">Evidence Reference</label>
                  <input
                    id="up-evid-ref"
                    type="text"
                    placeholder="e.g. RUN_20261013_FWD_30"
                    value={updateEvidenceRef}
                    onChange={(e) => setUpdateEvidenceRef(e.target.value)}
                    disabled={isUpdatingQual}
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="up-reason">Status Reason / Gate Assessment</label>
                <textarea
                  id="up-reason"
                  rows={2}
                  placeholder="Detail the rationale for approval, rejection, or ongoing forward testing..."
                  value={updateReason}
                  onChange={(e) => setUpdateReason(e.target.value)}
                  disabled={isUpdatingQual}
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowUpdateDrawer(false)}
                  disabled={isUpdatingQual}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isUpdatingQual}
                >
                  {isUpdatingQual ? 'Saving Assertion...' : 'Record Qualification Claim'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
