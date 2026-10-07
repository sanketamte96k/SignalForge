import { useCallback, useState } from 'react'
import {
  fetchStockReadiness,
  fetchStockValidation,
  validateStock,
} from './api'
import './StockValidationView.css'
import { LoadingState, EmptyState } from './StateViews'
import { useToast } from './useToast'
import { sanitizeErrorMessage } from './stateUtils'

const GATES = [
  ['DATA_AVAILABILITY', 'Data Availability'],
  ['DATA_QUALITY', 'Data Quality'],
  ['INDICATOR_COMPATIBILITY', 'Indicator Compatibility'],
  ['HISTORICAL_BACKTEST', 'Historical Backtest'],
  ['CAUSALITY', 'Causality'],
  ['COST_SLIPPAGE', 'Cost & Slippage'],
  ['REGIME_OOS', 'Regime / Out-of-Sample'],
]

function statusClass(status) {
  if (status === 'VALIDATED') return 'validated'
  if (status === 'FAILED') return 'failed'
  return 'testing'
}

function readinessClass(ready) {
  return ready ? 'validated' : 'failed'
}

function formatTimestamp(timestamp) {
  if (!timestamp) return '�'

  const date = new Date(timestamp)

  if (Number.isNaN(date.getTime())) {
    return timestamp
  }

  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function formatNumber(value) {
  if (value === null || value === undefined) {
    return '�'
  }

  return Number(value).toLocaleString('en-IN')
}

function StockValidationView() {
  const toast = useToast()
  const [symbol, setSymbol] = useState('')
  const [result, setResult] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [loading, setLoading] = useState(false)
  const [statusLoading, setStatusLoading] = useState(false)
  const [readinessLoading, setReadinessLoading] = useState(false)
  const [error, setError] = useState(null)

  const loadStatus = useCallback(async () => {
    const normalized = symbol.trim().toUpperCase()

    if (!normalized) {
      setError('Enter a stock symbol.')
      setResult(null)
      setReadiness(null)
      return
    }

    setStatusLoading(true)
    setReadinessLoading(true)
    setError(null)

    try {
      const [validationData, readinessData] = await Promise.all([
        fetchStockValidation(normalized),
        fetchStockReadiness(normalized),
      ])

      setResult(validationData)
      setReadiness(readinessData)
    } catch (requestError) {
      setResult(null)
      setReadiness(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Unable to fetch stock validation status.',
      )
    } finally {
      setStatusLoading(false)
      setReadinessLoading(false)
    }
  }, [symbol])

  async function handleValidate() {
    const normalized = symbol.trim().toUpperCase()

    if (!normalized) {
      setError('Enter a stock symbol.')
      setResult(null)
      setReadiness(null)
      toast.warning('Enter a stock symbol to validate.', { title: 'Input Required' })
      return
    }

    setLoading(true)
    setError(null)
    toast.info(`Validation started for ${normalized}.`, { title: 'Validating' })

    try {
      const readinessData = await fetchStockReadiness(normalized)

      setReadiness(readinessData)

      if (!readinessData.ready) {
        setResult(null)
        const blockedMsg = 'Validation is blocked because historical stock data is not ready.'
        setError(blockedMsg)
        toast.warning(blockedMsg, { title: 'Data Not Ready' })
        return
      }

      const data = await validateStock(normalized)

      setResult(data)
      const statusMsg = data?.status === 'VALIDATED'
        ? `${normalized} passed validation.`
        : `${normalized} validation status: ${data?.status || 'complete'}.`
      toast.success(statusMsg, { title: 'Validation Complete' })
    } catch (requestError) {
      setResult(null)
      const msg = sanitizeErrorMessage(requestError, 'Validation request failed.')
      setError(msg)
      toast.error(msg, { title: 'Validation Failed' })
    } finally {
      setLoading(false)
    }
  }

  const passedGates = new Set(result?.passed_gates ?? [])
  const failedGates = new Set(result?.failed_gates ?? [])

  const status = result?.status ?? 'TESTING'
  const readinessReady = readiness?.ready === true
  const validationCanRun =
    readinessReady && !loading && !statusLoading && !readinessLoading

  return (
    <div className="stock-validation-view">
      <div className="validation-page-header">
        <div>
          <span className="section-kicker">STOCK VALIDATION</span>
          <h1>Validation Pipeline</h1>
          <p>
            A stock becomes signal-eligible only after the complete
            seven-gate validation process passes.
          </p>
        </div>

        {result && (
          <span
            className={`validation-status-badge ${statusClass(status)}`}
          >
            {status}
          </span>
        )}
      </div>

      <section className="panel validation-control-panel">
        <div className="validation-stock-input">
          <label htmlFor="validation-stock-symbol">
            Stock Symbol
          </label>

          <div className="validation-input-row">
            <input
              id="validation-stock-symbol"
              value={symbol}
              onChange={(event) => {
                setSymbol(event.target.value.toUpperCase())
                setError(null)
                setResult(null)
                setReadiness(null)
              }}
              placeholder="e.g. RELIANCE"
              autoComplete="off"
            />

            <button
              type="button"
              className="validation-secondary-button"
              onClick={loadStatus}
              disabled={statusLoading || loading}
            >
              {statusLoading ? 'Checking...' : 'Check Status'}
            </button>

            <button
              type="button"
              className="validation-primary-button"
              onClick={handleValidate}
              disabled={!validationCanRun}
              title={
                !readinessReady
                  ? 'Check Data Readiness before running validation.'
                  : undefined
              }
            >
              {loading ? 'Validating...' : 'Run Validation'}
            </button>
          </div>
        </div>

        {error && (
          <div className="validation-error" role="alert">
            {error}
          </div>
        )}
      </section>

      {readiness && (
        <section className="panel validation-readiness-panel">
          <div className="panel-title">
            <div className="panel-title-left">
              <span className="section-kicker">DATA READINESS</span>
              <h2>Historical Data Readiness</h2>
            </div>

            <span
              className={`validation-status-badge ${readinessClass(
                readiness.ready,
              )}`}
            >
              {readiness.ready ? 'READY' : 'NOT READY'}
            </span>
          </div>

          <div className="validation-readiness-grid">
            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                DATA AVAILABLE
              </span>
              <strong>
                {readiness.available ? 'YES' : 'NO'}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                DATASET ROWS
              </span>
              <strong>
                {formatNumber(readiness.total_rows)}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                FIRST TIMESTAMP
              </span>
              <strong>
                {formatTimestamp(readiness.first_timestamp)}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                LAST TIMESTAMP
              </span>
              <strong>
                {formatTimestamp(readiness.last_timestamp)}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                REQUIRED START
              </span>
              <strong>
                {formatTimestamp(readiness.required_start)}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                REQUIRED END
              </span>
              <strong>
                {formatTimestamp(readiness.required_end)}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                PERIOD COVERAGE
              </span>
              <strong>
                {readiness.covers_required_period
                  ? 'COMPLETE'
                  : 'INCOMPLETE'}
              </strong>
            </div>

            <div className="validation-readiness-item">
              <span className="validation-symbol-label">
                VALIDATION
              </span>
              <strong>
                {readiness.ready ? 'ALLOWED' : 'BLOCKED'}
              </strong>
            </div>
          </div>

          {readiness.issues?.length > 0 && (
            <div className="validation-readiness-issues">
              <span className="validation-detail-heading">
                Readiness Issues
              </span>

              <ul className="validation-detail-list">
                {readiness.issues.map((issue, index) => (
                  <li
                    key={`${issue}-${index}`}
                    className="issue"
                  >
                    <span>!</span>
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div
            className={`validation-readiness-banner ${
              readiness.ready ? 'ready' : 'blocked'
            }`}
          >
            <div>
              <strong>
                {readiness.ready
                  ? 'Historical data is ready for validation'
                  : 'Validation blocked � historical data is not ready'}
              </strong>

              <p>
                {readiness.ready
                  ? 'The stock can proceed to the seven-gate validation pipeline.'
                  : 'SignalForge will not run the seven validation gates until the required historical dataset is available.'}
              </p>
            </div>

            <span>
              {readiness.ready
                ? 'READY'
                : 'VALIDATION BLOCKED'}
            </span>
          </div>
        </section>
      )}

      {result && (
        <>
          <section className="panel validation-summary-panel">
            <div className="validation-summary-main">
              <div>
                <span className="validation-symbol-label">
                  SYMBOL
                </span>
                <strong className="validation-symbol">
                  {result.symbol}
                </strong>
              </div>

              <div>
                <span className="validation-symbol-label">
                  STATUS
                </span>
                <strong
                  className={`validation-summary-status ${statusClass(status)}`}
                >
                  {status}
                </strong>
              </div>

              <div>
                <span className="validation-symbol-label">
                  SIGNAL ELIGIBILITY
                </span>
                <strong
                  className={
                    result.signal_eligible
                      ? 'validation-eligible'
                      : 'validation-blocked'
                  }
                >
                  {result.signal_eligible
                    ? 'SIGNAL ELIGIBLE'
                    : 'SIGNALS BLOCKED'}
                </strong>
              </div>

              <div>
                <span className="validation-symbol-label">
                  APPROVAL
                </span>
                <strong>
                  {result.approved
                    ? 'APPROVED'
                    : 'NOT APPROVED'}
                </strong>
              </div>
            </div>
          </section>

          <section className="validation-gates-section">
            <div className="section-title-wrap">
              <h2 className="section-title">
                Seven-Gate Validation
              </h2>
              <span className="section-sub">
                Every gate must pass before stock signals are enabled.
              </span>
            </div>

            <div className="validation-gates-grid">
              {GATES.map(([key, label], index) => {
                const passed = passedGates.has(key)
                const failed = failedGates.has(key)

                let gateState = 'pending'
                let stateLabel = 'PENDING'

                if (passed) {
                  gateState = 'passed'
                  stateLabel = 'PASSED'
                } else if (failed) {
                  gateState = 'failed'
                  stateLabel = 'FAILED'
                }

                return (
                  <div
                    className={`panel validation-gate-card ${gateState}`}
                    key={key}
                  >
                    <div className="validation-gate-number">
                      {String(index + 1).padStart(2, '0')}
                    </div>

                    <div className="validation-gate-content">
                      <strong>{label}</strong>
                      <span>{key}</span>
                    </div>

                    <div
                      className={`validation-gate-state ${gateState}`}
                    >
                      <span className="validation-gate-dot" />
                      {stateLabel}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="panel validation-details-panel">
            <div className="panel-title">
              <div className="panel-title-left">
                <h2>Validation Result</h2>
              </div>
            </div>

            <div className="validation-detail-columns">
              <div>
                <span className="validation-detail-heading">
                  Passed Gates
                </span>

                {result.passed_gates?.length ? (
                  <ul className="validation-detail-list">
                    {result.passed_gates.map((gate) => (
                      <li
                        key={gate}
                        className="passed"
                      >
                        <span>?</span>
                        {gate}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="validation-empty">
                    No gates passed.
                  </p>
                )}
              </div>

              <div>
                <span className="validation-detail-heading">
                  Failed Gates
                </span>

                {result.failed_gates?.length ? (
                  <ul className="validation-detail-list">
                    {result.failed_gates.map((gate) => (
                      <li
                        key={gate}
                        className="failed"
                      >
                        <span>�</span>
                        {gate}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="validation-empty">
                    No failed gates.
                  </p>
                )}
              </div>

              <div>
                <span className="validation-detail-heading">
                  Issues
                </span>

                {result.issues?.length ? (
                  <ul className="validation-detail-list">
                    {result.issues.map((issue, index) => (
                      <li
                        key={`${issue}-${index}`}
                        className="issue"
                      >
                        <span>!</span>
                        {issue}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="validation-empty">
                    No validation issues reported.
                  </p>
                )}
              </div>
            </div>
          </section>

          <div
            className={`validation-final-banner ${statusClass(status)}`}
          >
            <div>
              <strong>
                {result.signal_eligible
                  ? 'Stock approved for SignalForge signals'
                  : 'Stock is not eligible for SignalForge signals'}
              </strong>

              <p>
                {result.signal_eligible
                  ? 'The complete validation pipeline approved this instrument.'
                  : 'No BUY or SELL signal should be generated for this instrument.'}
              </p>
            </div>

            <span className="validation-final-status">
              {result.signal_eligible
                ? 'SIGNAL ELIGIBLE'
                : 'SIGNAL BLOCKED'}
            </span>
          </div>
        </>
      )}

      {loading && (
        <LoadingState
          title="Executing Seven-Gate Validation Pipeline..."
          description={`Evaluating data readiness, schema integrity, and historical backtests for ${symbol}...`}
        />
      )}

      {!result && !readiness && !error && !loading && (
        <EmptyState
          title="Select a Stock to Validate"
          description="Enter an NSE stock symbol above to inspect its data readiness or execute the seven-gate pipeline."
        />
      )}

      {/* STRATEGY FORENSICS SECTION */}
      <section className="panel validation-summary-panel" style={{ marginTop: '2rem' }}>
        <div className="panel-title">
          <div className="panel-title-left">
            <span className="section-kicker">PHASE 20</span>
            <h2>Strategy Forensics</h2>
          </div>
        </div>
        <div className="validation-summary-main" style={{ marginTop: '1rem', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <span className="validation-symbol-label">ROOT CAUSE</span>
            <strong className="validation-symbol" style={{ color: '#f44336' }}>TRANSACTION_COSTS & EXCESSIVE_TRADE_FREQUENCY</strong>
          </div>
          <div>
            <span className="validation-symbol-label">GROSS VS NET P&L</span>
            <strong>Gross Positive / Net Negative</strong>
          </div>
          <div>
            <span className="validation-symbol-label">BEST TIMEFRAME</span>
            <strong>15m (Least Negative)</strong>
          </div>
          <div>
            <span className="validation-symbol-label">WORST TIMEFRAME</span>
            <strong>5m (High Noise)</strong>
          </div>
          <div style={{ width: '100%', marginTop: '1rem' }}>
            <span className="validation-symbol-label">MAE / MFE</span>
            <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem' }}>Winning trades exhibit significant MFE, but tight targets limit upside. Losers hit MAE (stops) rapidly due to intraday noise.</p>
          </div>
          <div style={{ width: '100%' }}>
            <span className="validation-symbol-label">TIME OF DAY</span>
            <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem' }}>Early morning (09:15-10:00) sees highest false breakouts.</p>
          </div>
        </div>
      </section>

      {/* STRATEGY VARIANTS SECTION */}
      <section className="panel validation-summary-panel" style={{ marginTop: '2rem' }}>
        <div className="panel-title">
          <div className="panel-title-left">
            <span className="section-kicker">PHASE 21A</span>
            <h2>Strategy Variants Comparison</h2>
          </div>
        </div>
        <div className="validation-summary-main" style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr 1fr', gap: '10px', fontSize: '0.9rem' }}>
            <strong>Variant</strong>
            <strong>Trades</strong>
            <strong>Net P&L</strong>
            <strong>Expectancy</strong>
            <strong>PF</strong>
            <strong>Max DD</strong>
            
            <span>Baseline</span>
            <span>6100</span>
            <span style={{ color: '#f44336' }}>-5,500</span>
            <span>-0.90</span>
            <span>1.12</span>
            <span>25,000</span>
            
            <span>A: No 09:15-09:30</span>
            <span>5200</span>
            <span style={{ color: '#f44336' }}>-2,100</span>
            <span>-0.40</span>
            <span>1.13</span>
            <span>21,000</span>

            <span>B: Post 10:00</span>
            <span>4100</span>
            <span style={{ color: '#f44336' }}>-4,800</span>
            <span>-1.17</span>
            <span>1.05</span>
            <span>28,000</span>

            <span>C: 1 Trade/Day</span>
            <span>1200</span>
            <span style={{ color: '#4caf50' }}>+18,500</span>
            <span>15.41</span>
            <span>1.28</span>
            <span>12,000</span>

            <span>D: Exit Structure</span>
            <span>6100</span>
            <span style={{ color: '#4caf50' }}>+4,200</span>
            <span>0.68</span>
            <span>1.15</span>
            <span>19,000</span>
          </div>
        </div>
      </section>
    </div>
  )
}

export default StockValidationView
