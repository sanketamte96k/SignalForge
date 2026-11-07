import { useState, useEffect } from 'react'
import './TradingModeView.css'
import { fetchStrategySignal } from './api'

function TradingModeView() {
  const [selectedMode, setSelectedMode] = useState(() => {
    return localStorage.getItem('signalforge_trading_mode') || 'signal'
  })

  const [signalData, setSignalData] = useState(null)
  const [signalLoading, setSignalLoading] = useState(true)
  const [signalError, setSignalError] = useState(null)

  useEffect(() => {
    localStorage.setItem('signalforge_trading_mode', selectedMode)
  }, [selectedMode])

  const loadSignal = async () => {
    setSignalLoading(true)
    try {
      const data = await fetchStrategySignal('NIFTY 50', '15m')
      setSignalData(data)
      setSignalError(null)
    } catch (err) {
      setSignalError(err.message || 'Signal API unavailable')
    } finally {
      setSignalLoading(false)
    }
  }

  useEffect(() => {
    loadSignal()
  }, [])

  const handleModeChange = (mode) => {
    setSelectedMode(mode)
  }

  // Derived state for the signal card
  const displaySignal = signalData?.signal || 'N/A'
  const displayTime = signalData?.timestamp ? new Date(signalData.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'N/A'
  const displayPrice = signalData?.price ? signalData.price.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : 'N/A'
  const displaySymbol = signalData?.symbol || 'NIFTY 50'
  const displayTimeframe = signalData?.timeframe || '15m'

  const getFreshness = () => {
    if (signalLoading) {
      return { dot: 'gray', label: 'Checking Market Data...' }
    }
    if (signalError || !signalData) {
      return { dot: 'gray', label: 'DATA UNAVAILABLE' }
    }
    if (!signalData.timestamp) {
      return { dot: 'amber', label: 'UNVERIFIED' }
    }
    const rawTs = String(signalData.timestamp)
    const parsedTs = (rawTs.includes('+') || rawTs.endsWith('Z')) ? new Date(rawTs) : new Date(rawTs + '+05:30')
    if (isNaN(parsedTs.getTime())) {
      return { dot: 'amber', label: 'UNVERIFIED' }
    }
    const ageHours = (Date.now() - parsedTs.getTime()) / (1000 * 60 * 60)
    const isHistorical = signalData.status === 'HISTORICAL' || ageHours > 24
    if (isHistorical) {
      const formattedDate = parsedTs.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
      return { dot: 'amber', label: `HISTORICAL REPLAY — Data ended ${formattedDate}` }
    }
    return { dot: 'green', label: 'Market Data Live' }
  }

  const freshness = getFreshness()

  return (
    <div className="trading-mode-view">
      <header className="trading-mode-header">
        <h1>Trading Mode Selection</h1>
        <p>Select how you want to interact with SignalForge strategies.</p>
      </header>

      <div className="trading-mode-cards">
        {/* AUTO TRADING CARD */}
        <div 
          className={`trading-card auto-trading-card ${selectedMode === 'auto' ? 'selected' : ''}`}
          onClick={() => handleModeChange('auto')}
        >
          <div className="card-header">
            <h2>Auto Trading</h2>
            {selectedMode === 'auto' && <span className="selected-badge">Selected</span>}
          </div>
          <p className="card-desc">Automatically execute and manage trades during market hours.</p>

          <div className="live-status-lock">
            <span className="lock-icon">🔒</span>
            <strong>LIVE EXECUTION LOCKED</strong>
          </div>

          <div className="settings-grid">
            <div className="setting-item">
              <span className="setting-label">Paper Capital</span>
              <span className="setting-value">₹5,000</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Simulated Leverage</span>
              <span className="setting-value">5×</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Stock Universe</span>
              <span className="setting-value">Selected</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Risk Per Trade</span>
              <span className="setting-value editable">1%</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Daily Loss Limit</span>
              <span className="setting-value editable">2%</span>
            </div>
          </div>

          <div className="validation-status">
            <div className="status-item">
              <span className="status-dot green"></span>
              Strategy Validation
            </div>
            <div className="status-item">
              <span className="status-dot green"></span>
              Stock Validation
            </div>
            <div className="status-item">
              <span className="status-dot gray"></span>
              Broker Not Connected
            </div>
          </div>

          <button className="action-button disabled" disabled>
            Live Trading Not Enabled
          </button>
        </div>

        {/* SIGNAL ONLY CARD */}
        <div 
          className={`trading-card signal-only-card ${selectedMode === 'signal' ? 'selected' : ''}`}
          onClick={() => handleModeChange('signal')}
        >
          <div className="card-header">
            <h2>Signal Only</h2>
            {selectedMode === 'signal' && <span className="selected-badge">Selected</span>}
          </div>
          <p className="card-desc">Analyze signals and execute trades manually.</p>

          <div className="manual-label">
            <span>Manual Trading Mode</span>
          </div>

          <div className="signal-data-panel">
            <h3>Latest Strategy Signal ({displaySymbol} • {displayTimeframe})</h3>
            
            {signalLoading ? (
              <div className="signal-state">Loading signal data...</div>
            ) : signalError ? (
              <div className="signal-state error">
                <div style={{marginBottom: '12px'}}><span className="error-icon">⚠️</span> {signalError}</div>
                <button className="action-button secondary" onClick={loadSignal} style={{padding: '8px 16px', fontSize: '13px'}}>Retry Connection</button>
              </div>
            ) : (
              <div className="signal-details">
                {signalData?.status === 'HISTORICAL' && (
                  <div className="signal-row">
                    <span className="signal-label">Data Status</span>
                    <span className="signal-value" style={{color: 'var(--sf-orange)'}}>HISTORICAL</span>
                  </div>
                )}
                <div className="signal-row">
                  <span className="signal-label">Signal</span>
                  <span className={`signal-value ${displaySignal.toLowerCase().replace('/', '-')}`}>{displaySignal}</span>
                </div>
                <div className="signal-row">
                  <span className="signal-label">Time</span>
                  <span className="signal-value">{displayTime}</span>
                </div>
                <div className="signal-row">
                  <span className="signal-label">{signalData?.status === 'HISTORICAL' ? 'Last Historical Close' : 'Price'}</span>
                  <span className="signal-value">{displayPrice}</span>
                </div>
                
                {displaySignal !== 'NO_TRADE' && displaySignal !== 'N/A' && signalData?.entry_price != null && (
                  <div className="signal-row">
                    <span className="signal-label">Entry</span>
                    <span className="signal-value">{signalData.entry_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                {displaySignal !== 'NO_TRADE' && displaySignal !== 'N/A' && signalData?.stop_loss != null && (
                  <div className="signal-row">
                    <span className="signal-label">Stop Loss</span>
                    <span className="signal-value">{signalData.stop_loss.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                {displaySignal !== 'NO_TRADE' && displaySignal !== 'N/A' && signalData?.target_1 != null && (
                  <div className="signal-row">
                    <span className="signal-label">Target 1</span>
                    <span className="signal-value">{signalData.target_1.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                {displaySignal !== 'NO_TRADE' && displaySignal !== 'N/A' && signalData?.target_2 != null && (
                  <div className="signal-row">
                    <span className="signal-label">Target 2</span>
                    <span className="signal-value">{signalData.target_2.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="validation-status">
            <div className="status-item">
              <span className={`status-dot ${freshness.dot}`}></span>
              {freshness.label}
            </div>
            <div className="status-item">
              <span className="status-dot green"></span>
              Strategy Status: Active
            </div>
          </div>

          <button className="action-button secondary">
            Analyze Signals
          </button>
        </div>
      </div>
    </div>
  )
}

export default TradingModeView
