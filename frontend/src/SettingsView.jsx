/**
 * SettingsView.jsx — SignalForge Terminal Settings & Preferences
 *
 * Provides complete control over:
 * 1. General (default timeframe, auto-refresh, landing view)
 * 2. Chart Preferences (EMA, volume, RSI, crosshair, chart type)
 * 3. Notifications (trading signals, validation warnings, toast banners)
 * 4. Trading Preferences (risk per trade, position size, brokerage/slippage)
 * 5. Interface (compact mode, sidebar behavior)
 * 6. Data & API (real API connection test, data source status, unconfigured broker services)
 * 7. Reset (factory reset with accessible confirmation dialog)
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import './SettingsView.css'
import {
  TIMEFRAME_OPTIONS,
  REFRESH_INTERVAL_OPTIONS,
  LANDING_VIEW_OPTIONS,
  CHART_TYPE_OPTIONS,
  CROSSHAIR_OPTIONS,
  RISK_OPTIONS,
  BROKERAGE_OPTIONS,
  SIDEBAR_BEHAVIOR_OPTIONS,
  loadSettings,
  saveSettings,
  resetSettings,
  applySettingsToDOM,
} from './settingsUtils'
import { fetchHealth } from './api'
import { useToast } from './useToast'

export default function SettingsView({ onNavigate: _onNavigate }) {
  const toast = useToast()
  const [settings, setSettings] = useState(() => loadSettings())
  const [activeSection, setActiveSection] = useState('general')

  // API Health status state
  const [apiStatus, setApiStatus] = useState('checking') // 'connected' | 'disconnected' | 'checking'
  const [apiLatency, setApiLatency] = useState(null)
  const [isTestingApi, setIsTestingApi] = useState(false)

  // Reset confirmation modal state
  const [isResetModalOpen, setIsResetModalOpen] = useState(false)
  const resetConfirmBtnRef = useRef(null)
  const cancelBtnRef = useRef(null)

  // Apply settings to DOM on mount and changes
  useEffect(() => {
    applySettingsToDOM(settings)
  }, [settings])

  // Test backend API health
  const checkApiHealth = useCallback(async (isManual = false) => {
    if (isManual) {
      setApiStatus('checking')
    }
    const start = performance.now()
    try {
      const response = await fetchHealth()
      const latency = Math.round(performance.now() - start)
      setApiLatency(latency)
      if (response?.status === 'ok') {
        setApiStatus('connected')
        if (isManual) {
          toast.success(`SignalForge API is operational (${latency}ms latency).`)
        }
      } else {
        setApiStatus('disconnected')
        if (isManual) {
          toast.warning('SignalForge API returned an unexpected response.')
        }
      }
    } catch {
      setApiLatency(null)
      setApiStatus('disconnected')
      if (isManual) {
        toast.error('Unable to connect to SignalForge backend API.')
      }
    } finally {
      setIsTestingApi(false)
    }
  }, [toast])

  useEffect(() => {
    Promise.resolve().then(() => {
      checkApiHealth(false)
    })
  }, [checkApiHealth])

  // Generic setting updater with automatic persistence
  const updateSetting = useCallback((key, value) => {
    setSettings((prev) => {
      const updated = { ...prev, [key]: value }
      saveSettings(updated)
      return updated
    })
  }, [])

  // Manual save trigger
  const handleManualSave = useCallback(() => {
    saveSettings(settings)
    toast.success('Preferences saved successfully.')
  }, [settings, toast])

  // Reset confirmation trigger
  const handleConfirmReset = useCallback(() => {
    const freshDefaults = resetSettings()
    setSettings(freshDefaults)
    setIsResetModalOpen(false)
    toast.success('All settings have been reset to factory defaults.')
  }, [toast])

  // Handle modal keyboard navigation
  useEffect(() => {
    if (!isResetModalOpen) return

    const timer = setTimeout(() => {
      cancelBtnRef.current?.focus()
    }, 50)

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setIsResetModalOpen(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isResetModalOpen])

  // Scroll to section helper
  const scrollToSection = (sectionId) => {
    setActiveSection(sectionId)
    const element = document.getElementById(`settings-section-${sectionId}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="settings-view" role="region" aria-label="Terminal Settings">
      {/* --------------------------------------------------------------------
         Page Header
         -------------------------------------------------------------------- */}
      <div className="settings-header">
        <div className="settings-header-content">
          <span className="settings-kicker">Terminal Preferences</span>
          <h1 className="settings-title">Settings</h1>
          <p className="settings-subtitle">
            Configure default chart parameters, algorithmic notification rules,
            trading risk assumptions, and inspect data source connections.
          </p>
        </div>

        <div className="settings-header-actions">
          <button
            type="button"
            className="settings-btn settings-btn-danger"
            onClick={() => setIsResetModalOpen(true)}
            aria-label="Reset all settings to defaults"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            <span>Reset Defaults</span>
          </button>

          <button
            type="button"
            className="settings-btn settings-btn-primary"
            onClick={handleManualSave}
            aria-label="Save current preferences"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
              <polyline points="17 21 17 13 7 13 7 21" />
              <polyline points="7 3 7 8 15 8" />
            </svg>
            <span>Save Preferences</span>
          </button>
        </div>
      </div>

      {/* --------------------------------------------------------------------
         Section Sub-Navigation
         -------------------------------------------------------------------- */}
      <nav className="settings-nav-bar" aria-label="Settings Categories">
        {[
          ['general', 'General'],
          ['charts', 'Chart Preferences'],
          ['notifications', 'Notifications'],
          ['trading', 'Trading Preferences'],
          ['interface', 'Interface'],
          ['data-api', 'Data & API'],
          ['reset', 'Reset'],
        ].map(([id, label]) => (
          <button
            type="button"
            key={id}
            className={`settings-nav-tab ${activeSection === id ? 'active' : ''}`}
            onClick={() => scrollToSection(id)}
            aria-current={activeSection === id ? 'true' : undefined}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* --------------------------------------------------------------------
         Settings Sections
         -------------------------------------------------------------------- */}
      <div className="settings-sections">
        {/* ===================================================================
           1. GENERAL
           =================================================================== */}
        <section
          id="settings-section-general"
          className="settings-panel"
          aria-labelledby="heading-general"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </div>
              <h2 id="heading-general" className="settings-panel-title">
                1. General
              </h2>
            </div>
            <span className="settings-panel-badge">Workspace</span>
          </div>

          <div className="settings-panel-body">
            {/* Default Timeframe */}
            <div className="setting-row">
              <div className="setting-info">
                <label
                  htmlFor="setting-default-timeframe"
                  className="setting-label"
                >
                  Default Timeframe
                </label>
                <p className="setting-desc">
                  Default resolution applied when loading NIFTY and stock analysis charts.
                </p>
              </div>
              <div className="setting-control">
                <div
                  className="sf-segment-group"
                  role="radiogroup"
                  aria-label="Default Timeframe"
                >
                  {TIMEFRAME_OPTIONS.map((tf) => (
                    <button
                      type="button"
                      key={tf}
                      role="radio"
                      aria-checked={settings.defaultTimeframe === tf}
                      className={`sf-segment-btn ${
                        settings.defaultTimeframe === tf ? 'active' : ''
                      }`}
                      onClick={() => updateSetting('defaultTimeframe', tf)}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Auto Refresh Toggle & Interval */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Auto Refresh</span>
                <p className="setting-desc">
                  Periodically poll data feeds and scanner algorithms in the background.
                </p>
              </div>
              <div className="setting-control">
                {settings.autoRefresh && (
                  <select
                    id="setting-auto-refresh-interval"
                    className="sf-select"
                    value={settings.autoRefreshInterval}
                    onChange={(e) =>
                      updateSetting('autoRefreshInterval', e.target.value)
                    }
                    aria-label="Auto refresh interval"
                  >
                    {REFRESH_INTERVAL_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        Every {opt.label}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.autoRefresh}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting('autoRefresh', !settings.autoRefresh)
                  }
                  aria-label="Toggle auto refresh"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.autoRefresh ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Default Landing View */}
            <div className="setting-row">
              <div className="setting-info">
                <label
                  htmlFor="setting-default-landing-view"
                  className="setting-label"
                >
                  Default Landing View
                </label>
                <p className="setting-desc">
                  The initial workspace view shown when launching the SignalForge terminal.
                </p>
              </div>
              <div className="setting-control">
                <select
                  id="setting-default-landing-view"
                  className="sf-select"
                  value={settings.defaultLandingView}
                  onChange={(e) =>
                    updateSetting('defaultLandingView', e.target.value)
                  }
                >
                  {LANDING_VIEW_OPTIONS.map((view) => (
                    <option key={view} value={view}>
                      {view}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           2. CHART PREFERENCES
           =================================================================== */}
        <section
          id="settings-section-charts"
          className="settings-panel"
          aria-labelledby="heading-charts"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon cyan" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 3v18h18" />
                  <path d="m19 9-5 5-4-4-3 3" />
                </svg>
              </div>
              <h2 id="heading-charts" className="settings-panel-title">
                2. Chart Preferences
              </h2>
            </div>
            <span className="settings-panel-badge">Visualization</span>
          </div>

          <div className="settings-panel-body">
            {/* Show EMA */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Show Exponential Moving Averages (EMA)</span>
                <p className="setting-desc">
                  Render 20, 50, and 200 period moving average trend overlays on candlestick charts.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.showEma}
                  className="sf-toggle-btn"
                  onClick={() => updateSetting('showEma', !settings.showEma)}
                  aria-label="Toggle show EMA"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.showEma ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Show Volume */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Show Volume Histogram</span>
                <p className="setting-desc">
                  Display trading volume bars beneath candlestick price action.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.showVolume}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting('showVolume', !settings.showVolume)
                  }
                  aria-label="Toggle show volume"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.showVolume ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Show RSI */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Show Relative Strength Index (RSI 14)</span>
                <p className="setting-desc">
                  Display momentum oscillator sub-chart with 70/30 overbought/oversold boundaries.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.showRsi}
                  className="sf-toggle-btn"
                  onClick={() => updateSetting('showRsi', !settings.showRsi)}
                  aria-label="Toggle show RSI"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.showRsi ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Crosshair Mode */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Crosshair Mode</span>
                <p className="setting-desc">
                  Configure cursor targeting behavior when inspecting price points.
                </p>
              </div>
              <div className="setting-control">
                <div
                  className="sf-segment-group"
                  role="radiogroup"
                  aria-label="Crosshair mode"
                >
                  {CROSSHAIR_OPTIONS.map((mode) => (
                    <button
                      type="button"
                      key={mode.value}
                      role="radio"
                      aria-checked={settings.crosshair === mode.value}
                      className={`sf-segment-btn ${
                        settings.crosshair === mode.value ? 'active' : ''
                      }`}
                      onClick={() => updateSetting('crosshair', mode.value)}
                      title={mode.desc}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Default Chart Type */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Default Chart Type</span>
                <p className="setting-desc">
                  Primary charting style used across instrument inspection views.
                </p>
              </div>
              <div className="setting-control">
                <div
                  className="sf-segment-group"
                  role="radiogroup"
                  aria-label="Default chart type"
                >
                  {CHART_TYPE_OPTIONS.map((type) => (
                    <button
                      type="button"
                      key={type}
                      role="radio"
                      aria-checked={settings.defaultChartType === type}
                      className={`sf-segment-btn ${
                        settings.defaultChartType === type ? 'active' : ''
                      }`}
                      onClick={() => updateSetting('defaultChartType', type)}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           3. NOTIFICATIONS
           =================================================================== */}
        <section
          id="settings-section-notifications"
          className="settings-panel"
          aria-labelledby="heading-notifications"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                  <path d="M10 21h4" />
                </svg>
              </div>
              <h2 id="heading-notifications" className="settings-panel-title">
                3. Notifications
              </h2>
            </div>
            <span className="settings-panel-badge">Alerts</span>
          </div>

          <div className="settings-panel-body">
            {/* Trading Signal Notifications */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Trading Signal Notifications</span>
                <p className="setting-desc">
                  Emit alerts when new algorithmic BUY or SELL signals are identified by the scanner.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.tradingSignalNotifications}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting(
                      'tradingSignalNotifications',
                      !settings.tradingSignalNotifications,
                    )
                  }
                  aria-label="Toggle trading signal notifications"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.tradingSignalNotifications ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Validation Warnings */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Validation Gate Warnings</span>
                <p className="setting-desc">
                  Notify when a selected stock fails causality, slippage, or data quality gates.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.validationWarnings}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting(
                      'validationWarnings',
                      !settings.validationWarnings,
                    )
                  }
                  aria-label="Toggle validation warnings"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.validationWarnings ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Toast Notifications */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">In-Terminal Toast Notifications</span>
                <p className="setting-desc">
                  Display floating feedback banners for portfolio updates, saves, and errors.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.toastNotifications}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting(
                      'toastNotifications',
                      !settings.toastNotifications,
                    )
                  }
                  aria-label="Toggle toast notifications"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.toastNotifications ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           4. TRADING PREFERENCES
           =================================================================== */}
        <section
          id="settings-section-trading"
          className="settings-panel"
          aria-labelledby="heading-trading"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon orange" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                </svg>
              </div>
              <h2 id="heading-trading" className="settings-panel-title">
                4. Trading Preferences
              </h2>
            </div>
            <span className="settings-panel-badge">Risk Management</span>
          </div>

          <div className="settings-panel-body">
            {/* Risk Per Trade */}
            <div className="setting-row">
              <div className="setting-info">
                <label htmlFor="setting-risk-per-trade" className="setting-label">
                  Risk Per Trade
                </label>
                <p className="setting-desc">
                  Maximum allocated capital loss risk permitted per simulated trade position.
                </p>
              </div>
              <div className="setting-control">
                <div
                  className="sf-segment-group"
                  role="radiogroup"
                  aria-label="Risk per trade"
                >
                  {RISK_OPTIONS.map((risk) => (
                    <button
                      type="button"
                      key={risk}
                      role="radio"
                      aria-checked={settings.riskPerTrade === risk}
                      className={`sf-segment-btn ${
                        settings.riskPerTrade === risk ? 'active' : ''
                      }`}
                      onClick={() => updateSetting('riskPerTrade', risk)}
                    >
                      {risk}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Default Position Size */}
            <div className="setting-row">
              <div className="setting-info">
                <label
                  htmlFor="setting-default-position-size"
                  className="setting-label"
                >
                  Default Position Size
                </label>
                <p className="setting-desc">
                  Standard virtual order sizing value used in Paper Trading executions.
                </p>
              </div>
              <div className="setting-control">
                <div className="sf-input-prefix-wrap">
                  <span className="sf-input-prefix">₹</span>
                  <input
                    id="setting-default-position-size"
                    type="number"
                    min="1000"
                    step="5000"
                    className="sf-input sf-input-prefixed tabular-num"
                    value={settings.defaultPositionSize}
                    onChange={(e) =>
                      updateSetting(
                        'defaultPositionSize',
                        Math.max(0, Number(e.target.value)),
                      )
                    }
                    aria-label="Default position size in Rupees"
                  />
                </div>
              </div>
            </div>

            {/* Brokerage / Slippage Assumption */}
            <div className="setting-row">
              <div className="setting-info">
                <label
                  htmlFor="setting-brokerage-slippage"
                  className="setting-label"
                >
                  Brokerage & Slippage Assumption
                </label>
                <p className="setting-desc">
                  Simulated round-trip execution cost model for realistic P&L estimation.
                </p>
              </div>
              <div className="setting-control">
                <select
                  id="setting-brokerage-slippage"
                  className="sf-select"
                  value={settings.brokerageSlippage}
                  onChange={(e) =>
                    updateSetting('brokerageSlippage', e.target.value)
                  }
                >
                  {BROKERAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           5. INTERFACE
           =================================================================== */}
        <section
          id="settings-section-interface"
          className="settings-panel"
          aria-labelledby="heading-interface"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M9 3v18" />
                </svg>
              </div>
              <h2 id="heading-interface" className="settings-panel-title">
                5. Interface
              </h2>
            </div>
            <span className="settings-panel-badge">Layout</span>
          </div>

          <div className="settings-panel-body">
            {/* Compact Interface Toggle */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Compact Density Mode</span>
                <p className="setting-desc">
                  Condense row heights and padding to maximize information density for multi-monitor setups.
                </p>
              </div>
              <div className="setting-control">
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.compactInterface}
                  className="sf-toggle-btn"
                  onClick={() =>
                    updateSetting('compactInterface', !settings.compactInterface)
                  }
                  aria-label="Toggle compact interface density"
                >
                  <span className="sf-toggle-thumb" />
                </button>
                <span className="sf-toggle-status-text">
                  {settings.compactInterface ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            {/* Sidebar Behavior */}
            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">Sidebar Behavior</span>
                <p className="setting-desc">
                  Default navigation drawer state on desktop and mobile viewports.
                </p>
              </div>
              <div className="setting-control">
                <div
                  className="sf-segment-group"
                  role="radiogroup"
                  aria-label="Sidebar behavior"
                >
                  {SIDEBAR_BEHAVIOR_OPTIONS.map((opt) => (
                    <button
                      type="button"
                      key={opt.value}
                      role="radio"
                      aria-checked={settings.sidebarBehavior === opt.value}
                      className={`sf-segment-btn ${
                        settings.sidebarBehavior === opt.value ? 'active' : ''
                      }`}
                      onClick={() => updateSetting('sidebarBehavior', opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           6. DATA & API
           =================================================================== */}
        <section
          id="settings-section-data-api"
          className="settings-panel"
          aria-labelledby="heading-data-api"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon cyan" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
              </div>
              <h2 id="heading-data-api" className="settings-panel-title">
                6. Data & API
              </h2>
            </div>
            <span className="settings-panel-badge">Connectivity</span>
          </div>

          <div className="settings-panel-body">
            {/* Live API Connection Banner */}
            <div className="api-status-banner">
              <div className="api-status-details">
                <span
                  className={`api-status-dot ${apiStatus}`}
                  aria-hidden="true"
                />
                <div className="api-status-info">
                  <strong>
                    SignalForge Core REST API:{' '}
                    {apiStatus === 'connected'
                      ? 'Connected'
                      : apiStatus === 'checking'
                      ? 'Checking...'
                      : 'Disconnected'}
                  </strong>
                  <span>
                    {apiStatus === 'connected'
                      ? 'FastAPI backend responding normally'
                      : apiStatus === 'checking'
                      ? 'Validating server connection...'
                      : 'Backend server is unreachable (start FastAPI with uvicorn)'}
                  </span>
                </div>
              </div>

              <div className="api-status-meta">
                <span className="api-endpoint-badge">/api/health</span>
                {apiLatency !== null && (
                  <span className="api-latency-pill">{apiLatency} ms</span>
                )}
                <button
                  type="button"
                  className="settings-btn settings-btn-secondary"
                  disabled={isTestingApi}
                  onClick={() => {
                    setIsTestingApi(true)
                    checkApiHealth(true)
                  }}
                  aria-label="Test API connection"
                >
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                  </svg>
                  <span>{isTestingApi ? 'Testing...' : 'Test Connection'}</span>
                </button>
              </div>
            </div>

            {/* Service & Feed Inventory (Honest Statuses) */}
            <div className="service-inventory-grid">
              {/* Local Parquet Storage */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Local Parquet Engine</h3>
                    <span className="service-card-type">Data Store</span>
                  </div>
                  <span className="service-status-pill active">
                    ● ACTIVE
                  </span>
                </div>
                <p className="service-card-desc">
                  NSE 5-minute historical parquet candles (March 2024 dataset) loaded directly from local storage.
                </p>
              </div>

              {/* Indicator Engine */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Vectorized Indicator Engine</h3>
                    <span className="service-card-type">Analysis Core</span>
                  </div>
                  <span className="service-status-pill active">
                    ● ACTIVE
                  </span>
                </div>
                <p className="service-card-desc">
                  Numpy / Pandas quantitative pipeline for EMA, RSI, ATR, and breakout calculations.
                </p>
              </div>

              {/* Paper Trading Simulator */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Paper Trading Simulator</h3>
                    <span className="service-card-type">Execution Engine</span>
                  </div>
                  <span className="service-status-pill active">
                    ● ACTIVE
                  </span>
                </div>
                <p className="service-card-desc">
                  In-memory portfolio simulator with slippage modeling and trade ledger tracking.
                </p>
              </div>

              {/* Zerodha Kite Connect */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Zerodha Kite Connect</h3>
                    <span className="service-card-type">Broker Bridge</span>
                  </div>
                  <span className="service-status-pill not-configured">
                    ○ NOT CONFIGURED
                  </span>
                </div>
                <p className="service-card-desc">
                  Broker integration disabled. Requires Kite Connect API key and active access token in environment variables.
                </p>
              </div>

              {/* Upstox API */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Upstox Pro API</h3>
                    <span className="service-card-type">Broker Bridge</span>
                  </div>
                  <span className="service-status-pill not-configured">
                    ○ NOT CONFIGURED
                  </span>
                </div>
                <p className="service-card-desc">
                  Upstox V2 live trading gateway is not configured.
                </p>
              </div>

              {/* Angel One SmartAPI */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">Angel One SmartAPI</h3>
                    <span className="service-card-type">Broker Bridge</span>
                  </div>
                  <span className="service-status-pill not-configured">
                    ○ NOT CONFIGURED
                  </span>
                </div>
                <p className="service-card-desc">
                  SmartAPI client credentials and TOTP authenticator are not configured.
                </p>
              </div>

              {/* WebSocket Real-Time Feed */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">WebSocket Tick Feed</h3>
                    <span className="service-card-type">Live Market Feed</span>
                  </div>
                  <span className="service-status-pill not-configured">
                    ○ NOT CONFIGURED
                  </span>
                </div>
                <p className="service-card-desc">
                  Real-time tick streaming requires an authenticated live broker session.
                </p>
              </div>

              {/* FII / DII Institutional Flow */}
              <div className="service-card">
                <div className="service-card-top">
                  <div>
                    <h3 className="service-card-name">FII / DII Institutional Flow</h3>
                    <span className="service-card-type">Macro Data Feed</span>
                  </div>
                  <span className="service-status-pill unavailable">
                    ✕ UNAVAILABLE
                  </span>
                </div>
                <p className="service-card-desc">
                  External institutional flow feed requires a commercial exchange data subscription.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ===================================================================
           7. RESET
           =================================================================== */}
        <section
          id="settings-section-reset"
          className="settings-panel"
          aria-labelledby="heading-reset"
        >
          <div className="settings-panel-header">
            <div className="settings-panel-title-wrap">
              <div className="settings-panel-icon red" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                  <path d="M3 3v5h5" />
                </svg>
              </div>
              <h2 id="heading-reset" className="settings-panel-title">
                7. Reset
              </h2>
            </div>
            <span className="settings-panel-badge" style={{ color: 'var(--sf-red)', borderColor: 'rgba(255,79,94,0.3)', background: 'rgba(255,79,94,0.1)' }}>
              Danger Zone
            </span>
          </div>

          <div className="settings-panel-body">
            <div className="reset-box">
              <div className="reset-box-text">
                <strong>Reset All Terminal Preferences</strong>
                <p>
                  Revert all chart preferences, notification flags, risk thresholds, and layout
                  density options back to their factory defaults. Watchlists and paper trading history
                  will remain intact.
                </p>
              </div>

              <button
                type="button"
                className="settings-btn settings-btn-danger"
                onClick={() => setIsResetModalOpen(true)}
                aria-label="Open reset settings confirmation dialog"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M3 6h18" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                <span>Reset Settings</span>
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* --------------------------------------------------------------------
         Reset Confirmation Modal
         -------------------------------------------------------------------- */}
      {isResetModalOpen && (
        <div
          className="settings-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setIsResetModalOpen(false)
            }
          }}
          role="presentation"
        >
          <div
            className="settings-modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-modal-title"
          >
            <div className="settings-modal-header">
              <div className="settings-modal-icon" aria-hidden="true">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <h3 id="reset-modal-title" className="settings-modal-title">
                Reset Preferences to Defaults?
              </h3>
            </div>

            <div className="settings-modal-body">
              <p>
                Are you sure you want to reset all SignalForge settings?
              </p>
              <p>
                This will restore standard chart indicators, notification alerts, risk management
                tolerances, and interface density back to initial settings. This action cannot be undone.
              </p>
            </div>

            <div className="settings-modal-actions">
              <button
                type="button"
                className="settings-btn settings-btn-secondary"
                ref={cancelBtnRef}
                onClick={() => setIsResetModalOpen(false)}
              >
                Cancel
              </button>

              <button
                type="button"
                className="settings-btn settings-btn-danger-solid"
                ref={resetConfirmBtnRef}
                onClick={handleConfirmReset}
              >
                Yes, Reset All Settings
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
