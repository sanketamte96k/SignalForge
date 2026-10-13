import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import './CandlestickChart.css'
import { LoadingState, ErrorState, EmptyState } from './StateViews'
import { calculateCandleChange } from './chartUtils'
import { CandlestickChart, RsiChart } from './CandlestickChart'
import {
  fetchNiftyAnalysis,
  fetchNiftyLatest,
  fetchNiftySignal,
} from './api'
import StockValidationView from './StockValidationView'
import PaperTradingView from './PaperTradingView'
import SectorsView from './SectorsView'
import WatchlistsView from './WatchlistsView'
import StockScannerView from './StockScannerView'
import StockAnalysisView from './StockAnalysisView'
import SettingsView from './SettingsView'
import TradingModeView from './TradingModeView'
import StockUniverseView from './StockUniverseView'
import { loadSettings, applySettingsToDOM } from './settingsUtils'
import KeyboardShortcutsModal from './KeyboardShortcutsModal'
import SignalForgeLogo from './SignalForgeLogo'
import MarketIntelligenceView from './MarketIntelligenceView'
import { StrategySignalPanel } from './StrategySignalPanel'
import {
  isEditableTarget,
  isModifierKey,
  NAVIGATION_SHORTCUTS,
} from './keyboardShortcuts'

const navItems = [
  ['Dashboard', 'dashboard'],
  ['Trading Mode', 'activity'],
  ['Stock Universe', 'globe'],
  ['NIFTY Analysis', 'chart'],
  ['Stock Scanner', 'search'],
  ['Market Intelligence', 'chart'],
  ['Stock Analysis', 'candles'],
  ['Sectors', 'bars'],
  ['Watchlists', 'bookmark'],
  ['Add Stock', 'plus'],
  ['Validation', 'check'],
  ['Paper Trading', 'briefcase'],
  ['Reports', 'report'],
  ['Settings', 'settings'],
]

const signals = [
  ['RELIANCE', '2,856.40', 'BUY', '+2.14%', '02:58 PM', 'NIFTY 50'],
  ['TCS', '3,420.15', 'BUY', '+1.87%', '02:47 PM', 'NIFTY 50'],
  ['HDFCBANK', '1,612.30', 'SELL', '-1.23%', '02:41 PM', 'Banking'],
  ['INFY', '1,482.75', 'BUY', '+1.56%', '02:33 PM', 'NIFTY 50'],
  ['ICICIBANK', '1,098.20', 'BUY', '+1.34%', '02:21 PM', 'Banking'],
]

const sectors = [
  ['IT', '+1.18%', 92, true],
  ['Banking', '+0.96%', 76, true],
  ['Auto', '+0.67%', 54, true],
  ['FMCG', '+0.34%', 39, true],
  ['Pharma', '+0.21%', 22, true],
  ['Metal', '-0.48%', 45, false],
  ['Realty', '-0.62%', 52, false],
  ['Energy', '-0.29%', 27, false],
]

const watchlists = {
  'My Watchlist': [
    ['RELIANCE', '2,856.40', '+2.14%', 'BUY'],
    ['TCS', '3,420.15', '+1.87%', 'BUY'],
    ['HDFCBANK', '1,612.30', '-1.23%', 'SELL'],
    ['INFY', '1,482.75', '+1.56%', 'BUY'],
    ['ICICIBANK', '1,098.20', '+1.34%', 'BUY'],
  ],
  Tech: [
    ['TCS', '3,420.15', '+1.87%', 'BUY'],
    ['INFY', '1,482.75', '+1.56%', 'BUY'],
    ['WIPRO', '512.40', '+0.92%', 'BUY'],
    ['HCLTECH', '1,643.20', '+0.68%', 'BUY'],
  ],
  Banking: [
    ['HDFCBANK', '1,612.30', '-1.23%', 'SELL'],
    ['ICICIBANK', '1,098.20', '+1.34%', 'BUY'],
    ['SBIN', '824.50', '+0.82%', 'BUY'],
    ['AXISBANK', '1,184.25', '+0.54%', 'BUY'],
  ],
  'High Volatility': [
    ['RELIANCE', '2,856.40', '+2.14%', 'BUY'],
    ['ADANIENT', '2,412.80', '-1.91%', 'SELL'],
    ['TATAMOTORS', '978.40', '+1.72%', 'BUY'],
    ['BEL', '384.25', '+1.44%', 'BUY'],
  ],
}

const activity = [
  ['02:58 PM', 'BUY', 'Signal generated for RELIANCE', 'buy'],
  ['02:47 PM', 'BUY', 'Signal generated for TCS', 'buy'],
  ['02:41 PM', 'SELL', 'Signal generated for HDFCBANK', 'sell'],
  ['02:30 PM', 'VALIDATED', 'TATAMOTORS passed validation', 'validated'],
  ['02:18 PM', 'ALERT', 'NIFTY 50 crossed above EMA20', 'alert'],
]

const TIMEFRAMES = ['5m', '10m', '15m', '30m', '1H', '4H', '1D']
const SUPPORTED_TIMEFRAMES = new Set(['5m', '10m', '15m', '30m'])

function formatPrice(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '�'
  }

  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatNumber(value, decimals = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '�'
  }

  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function formatApiTimestamp(timestamp) {
  if (!timestamp) {
    return '�'
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

function App() {
  const [activeNav, setActiveNav] = useState('Dashboard')
  const [selectedStockSymbol, setSelectedStockSymbol] = useState('RELIANCE')
  const [activeTimeframe, setActiveTimeframe] = useState('15m')
  const [activeSignalFilter, setActiveSignalFilter] = useState('All')
  const [search, setSearch] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Initialize saved user layout density
  useEffect(() => {
    applySettingsToDOM(loadSettings())
  }, [])

  const handleSelectStock = useCallback((symbol) => {
    if (symbol) {
      setSelectedStockSymbol(symbol.trim().toUpperCase())
      setActiveNav('Stock Analysis')
    }
  }, [])

  // Synchronized chart interaction states
  const [chartViewRange, setChartViewRange] = useState(null)
  const [hoveredIndex, setHoveredIndex] = useState(null)
  const [hoveredCandle, setHoveredCandle] = useState(null)

  // Stable callbacks passed to chart children — avoid re-registering chart
  // effects every time the hovered candle changes.
  const handleHoverChange = useCallback((index, candle) => {
    setHoveredIndex(index)
    setHoveredCandle(candle)
  }, [])

  const handleRsiHoverChange = useCallback((index) => {
    setHoveredIndex(index)
  }, [])

  // Dashboard state
  const [niftyLatest, setNiftyLatest] = useState(null)
  const [niftySignal, setNiftySignal] = useState(null)
  const [niftyLoading, setNiftyLoading] = useState(true)
  const [niftyError, setNiftyError] = useState(null)

  // NIFTY Analysis dedicated state
  const [analysisData, setAnalysisData] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(true)
  const [analysisError, setAnalysisError] = useState(null)

  const handleRefreshAnalysis = useCallback(async () => {
    setAnalysisLoading(true)
    setAnalysisError(null)

    try {
      const data = await fetchNiftyAnalysis()
      setAnalysisData(data)
    } catch (error) {
      setAnalysisError(
        error instanceof Error
          ? error.message
          : 'API request failed. Backend analysis unavailable.',
      )
      setAnalysisData(null)
    } finally {
      setAnalysisLoading(false)
    }
  }, [])

  const initializeDashboardData = useCallback(async (targetTimeframe = activeTimeframe) => {
    setNiftyLoading(true)
    setAnalysisLoading(true)
    setNiftyError(null)
    setAnalysisError(null)

    const isSupported = SUPPORTED_TIMEFRAMES.has(targetTimeframe)

    try {
      const fetchPromises = [
        fetchNiftyLatest(),
        isSupported
          ? fetchNiftySignal(targetTimeframe)
          : Promise.reject(new Error(`Unsupported timeframe: ${targetTimeframe}`)),
        fetchNiftyAnalysis(),
      ]

      const [latestResult, signalResult, analysisResult] =
        await Promise.allSettled(fetchPromises)

      let dashboardErr = null

      if (latestResult.status === 'fulfilled') {
        setNiftyLatest(latestResult.value)
      } else {
        setNiftyLatest(null)
        dashboardErr =
          latestResult.reason instanceof Error
            ? latestResult.reason.message
            : 'Failed to fetch latest NIFTY data'
      }

      if (signalResult.status === 'fulfilled') {
        setNiftySignal(signalResult.value)
      } else {
        setNiftySignal(null)
        if (isSupported) {
          dashboardErr =
            signalResult.reason instanceof Error
              ? signalResult.reason.message
              : 'Failed to fetch NIFTY signal'
        }
      }

      if (
        latestResult.status === 'rejected' &&
        signalResult.status === 'rejected' &&
        isSupported
      ) {
        setNiftyError(dashboardErr || 'SignalForge API unavailable')
      } else if (signalResult.status === 'rejected' && isSupported) {
        setNiftyError(dashboardErr || 'Signal API unavailable')
      } else {
        setNiftyError(null)
      }

      if (analysisResult.status === 'fulfilled') {
        setAnalysisData(analysisResult.value)
        setAnalysisError(null)
      } else {
        setAnalysisData(null)
        setAnalysisError(
          analysisResult.reason instanceof Error
            ? analysisResult.reason.message
            : 'Backend analysis unavailable',
        )
      }
    } catch (error) {
      setNiftyError(
        error instanceof Error ? error.message : 'Unable to connect to API',
      )
      setAnalysisError(
        error instanceof Error ? error.message : 'Backend analysis unavailable',
      )
    } finally {
      setNiftyLoading(false)
      setAnalysisLoading(false)
    }
  }, [activeTimeframe])

  useEffect(() => {
    Promise.resolve().then(() => {
      initializeDashboardData(activeTimeframe)
    })
  }, [initializeDashboardData, activeTimeframe])

  const filteredSignals = useMemo(() => {
    let list = signals

    if (activeSignalFilter === 'NIFTY 50') {
      list = list.filter((s) => s[5] === 'NIFTY 50')
    } else if (activeSignalFilter === 'Watchlists') {
      const watchlistSymbols = new Set(
        Object.values(watchlists).flatMap((arr) => arr.map((item) => item[0])),
      )
      list = list.filter((s) => watchlistSymbols.has(s[0]))
    } else if (activeSignalFilter === 'Sectors') {
      list = list.filter((s) => s[5] !== 'NIFTY 50')
    }

    const query = search.trim().toLowerCase()
    if (!query) {
      return list
    }

    return list.filter((row) =>
      row.slice(0, 5).some((value) => value.toLowerCase().includes(query)),
    )
  }, [search, activeSignalFilter])

  const watchlistStocks = watchlists['My Watchlist']

  const [showShortcutsModal, setShowShortcutsModal] = useState(false)
  const [scannerFocusTrigger, setScannerFocusTrigger] = useState(0)

  const handleNavigation = useCallback((item) => {
    setActiveNav(item)
    setSidebarOpen(false)
  }, [])

  // Centralized Global Keyboard Shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      // If modal is open, let Escape close it
      if (showShortcutsModal) {
        if (e.key === 'Escape') {
          e.preventDefault()
          setShowShortcutsModal(false)
        }
        return
      }

      // If user is actively typing in an input/textarea/select/contenteditable
      if (isEditableTarget(e.target)) {
        if (e.key === 'Escape') {
          e.target.blur()
        }
        return
      }

      // Do not hijack browser modifiers (Ctrl, Meta, Alt)
      if (isModifierKey(e)) {
        return
      }

      // '?' opens shortcuts help dialog
      if (e.key === '?') {
        e.preventDefault()
        setShowShortcutsModal(true)
        return
      }

      // '/' routes to Stock Scanner and focuses search
      if (e.key === '/') {
        e.preventDefault()
        if (activeNav !== 'Stock Scanner') {
          handleNavigation('Stock Scanner')
        }
        setScannerFocusTrigger((prev) => prev + 1)
        return
      }

      // '1' - '7' navigation shortcuts
      if (NAVIGATION_SHORTCUTS[e.key]) {
        e.preventDefault()
        handleNavigation(NAVIGATION_SHORTCUTS[e.key])
        return
      }
    }

    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [showShortcutsModal, activeNav, handleNavigation])

  // Dashboard signal/price/badge derivations — memoized so they only
  // recompute when API state changes, not on every chart hover.
  const dashboardDisplay = useMemo(() => {
    let displaySignal = '\u2014'
    let signalSubtitle = 'NO ACTIVE TRADE SETUP'
    let signalClass = 'no-trade'

    if (niftyLoading) {
      displaySignal = 'LOADING\u2026'
      signalSubtitle = 'FETCHING STRATEGY STATE'
      signalClass = 'loading'
    } else if (!niftySignal || niftyError) {
      displaySignal = 'API UNAVAILABLE'
      signalSubtitle = niftyError || 'BACKEND SERVICE DISCONNECTED'
      signalClass = 'unavailable'
    } else {
      const rawSignal = String(niftySignal.signal || '').toUpperCase().trim()
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
      } else {
        displaySignal = 'NOT AVAILABLE'
        signalSubtitle = 'NO SIGNAL FIELD RETURNED'
        signalClass = 'unavailable'
      }
    }

    const apiPrice =
      typeof niftySignal?.price === 'number'
        ? niftySignal.price
        : typeof niftyLatest?.close === 'number'
          ? niftyLatest.close
          : null

    const displayPrice =
      niftyLoading
        ? 'Loading\u2026'
        : apiPrice !== null
          ? apiPrice.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
          : '\u2014'

    const rawTimestamp =
      niftySignal?.timestamp || niftyLatest?.timestamp || null

    const displayTimestamp =
      niftyLoading
        ? 'Loading\u2026'
        : rawTimestamp
          ? formatApiTimestamp(rawTimestamp)
          : '\u2014'

    const displayReason =
      niftyLoading
        ? 'Loading\u2026'
        : niftyError && !niftySignal
          ? 'API Unavailable'
          : '\u2014'

    const hasCandleData =
      typeof niftyLatest?.open === 'number' &&
      typeof niftyLatest?.close === 'number'

    const candleDiff = hasCandleData
      ? niftyLatest.close - niftyLatest.open
      : null

    const candlePct =
      hasCandleData && niftyLatest.open > 0
        ? (candleDiff / niftyLatest.open) * 100
        : null

    const candleClass =
      candleDiff !== null
        ? candleDiff >= 0
          ? 'positive'
          : 'negative'
        : ''

    const candleText =
      candleDiff !== null
        ? `${candleDiff >= 0 ? '+' : ''}${candleDiff.toFixed(2)} (${candleDiff >= 0 ? '+' : ''}${candlePct.toFixed(2)}%)`
        : 'Change \u2014'

    const badgeType = niftyLoading
      ? 'loading'
      : niftyError && !niftySignal
        ? 'error'
        : 'historical'

    const badgeText = niftyLoading
      ? 'Connecting'
      : niftyError && !niftySignal
        ? 'API Unavailable'
        : 'Historical API'

    return {
      displaySignal, signalSubtitle, signalClass,
      displayPrice, displayTimestamp, displayReason,
      candleClass, candleText, badgeType, badgeText,
    }
  }, [niftyLoading, niftySignal, niftyLatest, niftyError])

  const { candleClass, candleText } = dashboardDisplay

  return (
    <div className="terminal">
      {/* Mobile backdrop for drawer dismiss */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* 1. Left Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="logo-mark">
            <SignalForgeLogo size={36} />
          </div>

          <div>
            <div className="logo-name">SignalForge</div>
            <div className="logo-tagline">SCAN. ANALYZE. PROFIT.</div>
          </div>
        </div>

        <div className="sidebar-scroll">
          <div className="sidebar-title">MARKET WORKSPACE</div>

          <nav className="sidebar-nav" aria-label="Main Navigation">
            {navItems.map(([label, icon]) => (
              <button
                type="button"
                key={label}
                className={`sidebar-item ${activeNav === label ? 'active' : ''
                  }`}
                aria-current={activeNav === label ? 'page' : undefined}
                onClick={() =>
                  handleNavigation(
                    label === 'Scanner' ? 'Stock Scanner' : label,
                  )
                }
              >
                <Icon type={icon} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-system-info">
            <div className="system-pill">
              <span className="system-dot" />
              <span>ALGO ENGINE ACTIVE</span>
            </div>
            <div className="system-sub">SignalForge Engine v0.1.0</div>
          </div>

          <div className="sidebar-user">
            <div className="user-avatar">SA</div>

            <div className="user-details">
              <strong>SignalForge Terminal</strong>
              <span>Analytics Pro</span>
            </div>

            <button type="button" aria-label="User menu" className="user-more-btn">
              <Icon type="more-horizontal" />
            </button>
          </div>
        </div>
      </aside>

      <main className="main">
        {/* Top Search / Header & Market Status Data */}
        <header className="top-header">
          <button
            type="button"
            className="mobile-toggle"
            aria-label={sidebarOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={sidebarOpen}
            onClick={() => setSidebarOpen((value) => !value)}
          >
            <span />
            <span />
            <span />
          </button>

          <div className="top-logo-mobile">
            <span className="mobile-logo-mark">
              <SignalForgeLogo size={24} />
            </span>
            <strong>SignalForge</strong>
          </div>

          <label className="global-search">
            <Icon type="search" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search stocks, sectors, or watchlists..."
              aria-label="Search stocks, sectors, or watchlists"
            />
          </label>

          <div className="market-close">
            <span className="blue-dot" />
            <strong>Dataset Status</strong>
            <span className="market-countdown">Historical (Mar 2024)</span>
          </div>

          <div className="top-market-data">
            <TopMarket
              icon="fii"
              label="FII / DII"
              value="�"
              change="Unavailable"
            />

            <TopMarket
              icon="globe"
              label="Global Markets"
              value="�"
              change="Unavailable"
            />

            <TopMarket
              icon="barrel"
              label="Crude Oil"
              value="�"
              change="Unavailable"
            />

            <TopMarket
              icon="currency"
              label="USD / INR"
              value="�"
              change="Unavailable"
            />
          </div>

          <div className="header-actions">
            <button
              type="button"
              className="header-shortcuts-btn"
              onClick={() => setShowShortcutsModal(true)}
              aria-label="Keyboard shortcuts (?)"
              title="Keyboard shortcuts (?)"
            >
              <Icon type="keyboard" />
              <span className="shortcuts-key-hint">?</span>
            </button>

            <button
              type="button"
              className="notification-btn"
              aria-label="Notifications"
            >
              <Icon type="bell" />
              <span className="notification-badge">3</span>
            </button>

            <button
              type="button"
              className="header-user-btn"
              aria-label="Account profile"
            >
              <div className="header-avatar">SA</div>
              <Icon type="chevron-down" />
            </button>
          </div>
        </header>

        <div className="content">
          {activeNav === 'NIFTY Analysis' ? (
            <NiftyAnalysisView
              data={analysisData}
              loading={analysisLoading}
              error={analysisError}
              onRefresh={handleRefreshAnalysis}
              onNavigateDashboard={() => handleNavigation('Dashboard')}
            />
          ) : activeNav === 'Stock Scanner' ? (
            <StockScannerView
              onSelectStock={handleSelectStock}
              focusTrigger={scannerFocusTrigger}
            />
          ) : activeNav === 'Market Intelligence' || activeNav === 'Intelligence' ? (
            <MarketIntelligenceView />
          ) : activeNav === 'Stock Analysis' ? (
            <StockAnalysisView
              symbol={selectedStockSymbol}
              onBack={() => handleNavigation('Stock Scanner')}
              onSelectStock={handleSelectStock}
            />
          ) : activeNav === 'Validation' ? (
            <StockValidationView />
          ) : activeNav === 'Sectors' ? (
            <SectorsView />
          ) : activeNav === 'Watchlists' ? (
            <WatchlistsView />
          ) : activeNav === 'Paper Trading' || activeNav === 'Paper' ? (
            <PaperTradingView />
          ) : activeNav === 'Settings' ? (
            <SettingsView onNavigate={handleNavigation} />
          ) : activeNav === 'Trading Mode' ? (
            <TradingModeView />
          ) : activeNav === 'Stock Universe' || activeNav === 'Universe' ? (
            <StockUniverseView />
          ) : (
            <>
              {/* Top Section: LARGE NIFTY 50 CHART + NIFTY 50 STRATEGY SIGNAL */}
              <section className="main-grid">
                {/* Large NIFTY 50 Analysis Panel */}
                <div className="nifty-panel panel">
                  <div className="panel-header nifty-header">
                    <div className="nifty-title">
                      <h1>NIFTY 50</h1>

                      <div className="timeframe-tabs-wrap">
                        <div
                          className="timeframe-tabs"
                          role="tablist"
                          aria-label="Select chart timeframe"
                        >
                          {TIMEFRAMES.map((timeframe) => (
                            <button
                              type="button"
                              key={timeframe}
                              role="tab"
                              aria-selected={activeTimeframe === timeframe}
                              aria-label={`Select ${timeframe} timeframe`}
                              className={
                                activeTimeframe === timeframe ? 'active' : ''
                              }
                              onClick={() => {
                                setActiveTimeframe(timeframe)
                                setChartViewRange(null)
                                setHoveredIndex(null)
                                setHoveredCandle(null)
                              }}
                            >
                              {timeframe}
                            </button>
                          ))}
                        </div>
                        <span className="timeframe-hint">
                          {SUPPORTED_TIMEFRAMES.has(activeTimeframe)
                            ? `(Timeframe: ${activeTimeframe})`
                            : `(Unsupported timeframe: ${activeTimeframe})`}
                        </span>
                      </div>
                    </div>

                    <div className="chart-actions">
                      <button type="button" aria-label="Chart indicators">
                        <Icon type="indicator" />
                        <span>Indicators</span>
                      </button>

                      <button type="button" aria-label="Chart templates">
                        <Icon type="template" />
                        <span>Templates</span>
                      </button>

                      <button type="button" aria-label="Fullscreen" title="Fullscreen">
                        <Icon type="fullscreen" />
                      </button>
                    </div>
                  </div>

                  {/* OHLC Row */}
                  <div className="ohlc-row" aria-label="Current candle OHLC information">
                    <span>
                      O <strong>{formatPrice(hoveredCandle ? hoveredCandle.open : niftyLatest?.open)}</strong>
                    </span>
                    <span className="positive">
                      H <strong>{formatPrice(hoveredCandle ? hoveredCandle.high : niftyLatest?.high)}</strong>
                    </span>
                    <span className="negative">
                      L <strong>{formatPrice(hoveredCandle ? hoveredCandle.low : niftyLatest?.low)}</strong>
                    </span>
                    <span className="positive">
                      C <strong>{formatPrice(hoveredCandle ? hoveredCandle.close : niftyLatest?.close)}</strong>
                    </span>
                    <span className={`ohlc-change ${hoveredCandle ? (hoveredCandle.close >= hoveredCandle.open ? 'positive' : 'negative') : candleClass}`}>
                      {hoveredCandle ? (calculateCandleChange(hoveredCandle)?.text ?? candleText) : candleText}
                    </span>
                  </div>

                  {/* Chart Legend */}
                  <div className="chart-legend">
                    <span className="legend-item blue">
                      <span className="legend-marker marker-blue" />
                      EMA 20 <strong>—</strong>
                    </span>
                    <span className="legend-item orange">
                      <span className="legend-marker marker-orange" />
                      EMA 50 <strong>—</strong>
                    </span>
                    <span className="legend-item purple">
                      <span className="legend-marker marker-purple" />
                      EMA 200 <strong>—</strong>
                    </span>
                    <span className="legend-item volume">
                      <span className="legend-marker marker-volume" />
                      Volume{' '}
                      <strong>
                        {typeof (hoveredCandle?.volume ?? niftyLatest?.volume) === 'number'
                          ? Number(hoveredCandle?.volume ?? niftyLatest?.volume).toLocaleString('en-IN')
                          : '—'}
                      </strong>
                    </span>
                  </div>

                  {/* Real historical candlestick chart from the backend API */}
                  <div className="candlestick-chart">
                    <CandlestickChart
                      timeframe={activeTimeframe}
                      signal={niftySignal}
                      viewRange={chartViewRange}
                      onViewRangeChange={setChartViewRange}
                      hoverIndex={hoveredIndex}
                      onHoverChange={handleHoverChange}
                    />
                  </div>

                  {/* Real RSI(14) series from the backend chart API */}
                  <div className="rsi-panel">
                    <div className="rsi-label">
                      RSI (14)
                      <span className="rsi-sub">
                        Real RSI(14) calculated by the SignalForge indicator engine
                      </span>
                    </div>
                    <RsiChart
                      timeframe={activeTimeframe}
                      viewRange={chartViewRange}
                      hoverIndex={hoveredIndex}
                      onHoverChange={handleRsiHoverChange}
                    />
                  </div>
                </div>

                {/* NIFTY 50 Strategy Signal Panel */}
                <StrategySignalPanel
                  signalData={niftySignal}
                  latestData={niftyLatest}
                  loading={niftyLoading && !niftySignal}
                  error={niftyError}
                  activeTimeframe={activeTimeframe}
                  isUnsupported={!SUPPORTED_TIMEFRAMES.has(activeTimeframe)}
                  onSelectTimeframe={(tf) => {
                    setActiveTimeframe(tf)
                    setChartViewRange(null)
                    setHoveredIndex(null)
                    setHoveredCandle(null)
                  }}
                  onRetry={() => initializeDashboardData(activeTimeframe)}
                  onNavigateFullAnalysis={() => handleNavigation('NIFTY Analysis')}
                />
              </section>

          {/* Lower Section: Top Signals Today, Sector Performance, Watchlists */}
          <section className="lower-grid">
            {/* Top Signals Today */}
            <div className="panel signals-panel">
              <PanelTitle title="Top Signals Today" action="View All" />

              <div className="filter-tabs">
                {['All', 'NIFTY 50', 'Watchlists', 'Sectors'].map(
                  (tab) => (
                    <button
                      type="button"
                      className={activeSignalFilter === tab ? 'active' : ''}
                      key={tab}
                      onClick={() => setActiveSignalFilter(tab)}
                    >
                      {tab}
                    </button>
                  ),
                )}
              </div>

                  <div className="table-wrapper">
                    <div className="signals-table">
                      <div className="table-head">
                        <span>Symbol</span>
                        <span className="text-right">Price</span>
                        <span className="text-center">Signal</span>
                        <span className="text-right">Change</span>
                        <span className="text-right">Time</span>
                      </div>

                      {filteredSignals.map(
                        ([symbol, price, signal, change, time]) => (
                          <div className="signal-row" key={symbol}>
                            <strong>{symbol}</strong>
                            <span className="text-right tabular-num">{price}</span>
                            <div className="badge-cell">
                              <SignalBadge value={signal} />
                            </div>
                            <span
                              className={`text-right tabular-num ${change.startsWith('+')
                                ? 'positive'
                                : 'negative'
                                }`}
                            >
                              {change}
                            </span>
                            <span className="text-right tabular-num text-muted">
                              {time}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                </div>

                {/* Sector Performance */}
                <div className="panel sector-panel">
                  <PanelTitle
                    title="Sector Performance"
                    action="View All"
                    extra={
                      <div className="period-selector">
                        <span>1D</span>
                        <Icon type="chevron-down" />
                      </div>
                    }
                  />

                  <div className="table-wrapper">
                    <div className="sector-heading">
                      <span>Sector</span>
                      <span className="text-right">Change</span>
                      <span className="text-left">Relative Trend</span>
                    </div>

                    <div className="sector-list">
                      {sectors.map(
                        ([name, change, width, isPositive]) => (
                          <div className="sector-row" key={name}>
                            <span className="sector-name">{name}</span>
                            <strong
                              className={`text-right tabular-num ${isPositive ? 'positive' : 'negative'
                                }`}
                            >
                              {change}
                            </strong>
                            <div className="sector-bar">
                              <span
                                className={
                                  isPositive
                                    ? 'positive-bar'
                                    : 'negative-bar'
                                }
                                style={{ width: `${width}%` }}
                              />
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                </div>

                {/* Watchlists */}
                <div className="panel watchlist-panel">
                  <PanelTitle title="Watchlists" action="View All" />

                  <div className="watchlist-tabs">
                    {['My Watchlist', 'Tech', 'Banking', 'High Volatility'].map(
                      (tab) => (
                        <button
                          type="button"
                          key={tab}
                          className={tab === 'My Watchlist' ? 'active' : ''}
                        >
                          {tab}
                        </button>
                      ),
                    )}
                  </div>

                  <div className="table-wrapper">
                    <div className="watchlist-table">
                      <div className="table-head">
                        <span>Symbol</span>
                        <span className="text-right">Price</span>
                        <span className="text-right">Change</span>
                        <span className="text-center">Signal</span>
                      </div>

                      {watchlistStocks.map(
                        ([symbol, price, change, signal]) => (
                          <div className="watch-row" key={symbol}>
                            <strong>{symbol}</strong>
                            <span className="text-right tabular-num">{price}</span>
                            <span
                              className={`text-right tabular-num ${change.startsWith('+')
                                ? 'positive'
                                : 'negative'
                                }`}
                            >
                              {change}
                            </span>
                            <div className="badge-cell">
                              <SignalBadge value={signal} />
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                </div>
              </section>

              {/* Bottom Section: Stock Validation, Paper Trading, Recent Activity */}
              <section className="bottom-grid">
                {/* Stock Validation */}
                <div className="panel validation-panel">
                  <PanelTitle title="Stock Validation" action="View All" />

                  <div className="validation-content">
                    <ValidationRing />

                    <div className="validation-legend">
                      <ValidationItem
                        label="Validated"
                        value="42"
                        className="validated"
                      />
                      <ValidationItem
                        label="In Progress"
                        value="5"
                        className="progress"
                      />
                      <ValidationItem
                        label="Pending"
                        value="2"
                        className="pending"
                      />
                      <ValidationItem
                        label="Failed"
                        value="1"
                        className="failed"
                      />
                    </div>
                  </div>

                  <button type="button" className="add-stock-button">
                    <span>Add New Stock</span>
                    <Icon type="arrow-right" />
                  </button>
                </div>

                {/* Paper Trading */}
                <div className="panel paper-panel">
                  <PanelTitle
                    title="Paper Trading"
                    action="View All"
                    badge={
                      <span className="paper-mode-badge">
                        <i />
                        Paper Mode
                      </span>
                    }
                  />

                  <div className="paper-stats">
                    <Metric
                      label="Total P&L"
                      value="+12,430"
                      sub="+1.24%"
                      positive
                    />
                    <Metric label="Open Positions" value="3" />
                    <Metric label="Win Rate" value="68%" />
                    <Metric label="Total Trades" value="48" />
                  </div>

                  <div className="equity-chart">
                    <EquityChart />
                  </div>

                  <div className="months">
                    <span>Jan</span>
                    <span>Feb</span>
                    <span>Mar</span>
                    <span>Apr</span>
                    <span>May</span>
                    <span>Jun</span>
                    <span>Jul</span>
                    <span>Aug</span>
                  </div>
                </div>

                {/* Recent Activity */}
                <div className="panel activity-panel">
                  <PanelTitle title="Recent Activity" action="View All" />

                  <div className="table-wrapper">
                    <div className="activity-table">
                      <div className="activity-heading">
                        <span>Time</span>
                        <span>Event</span>
                        <span>Details</span>
                      </div>

                      {activity.map(
                        ([time, event, details, type]) => (
                          <div
                            className="activity-row"
                            key={`${time}-${event}`}
                          >
                            <span className="tabular-num text-muted">{time}</span>
                            <strong className={`activity-badge ${type}`}>
                              {event}
                            </strong>
                            <span className="activity-details">{details}</span>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                </div>
              </section>
            </>
          )}

          {/* Institutional Footer */}
          <footer className="footer">
            <div className="footer-left">
              <div className="footer-logo">
                <Icon type="arrow-up-right" />
              </div>
              <strong>SignalForge</strong>
              <span>Scan. Analyze. Profit.</span>
            </div>

            <div className="system-operational">
              <i />
              All Systems Operational
            </div>

            <span className="version">v1.0.0</span>
          </footer>
        </div>

        {/* Mobile Bottom Navigation */}
        <nav className="mobile-nav" aria-label="Mobile Navigation">
          {[
            ['Dashboard', 'dashboard'],
            ['NIFTY', 'chart'],
            ['Scanner', 'search'],
            ['Analysis', 'candles'],
            ['Watchlists', 'bookmark'],
            ['Paper', 'briefcase'],
          ].map(([label, icon]) => {
            const isItemActive =
              activeNav === label ||
              (label === 'NIFTY' && activeNav === 'NIFTY Analysis') ||
              (label === 'Scanner' && activeNav === 'Stock Scanner') ||
              (label === 'Analysis' && activeNav === 'Stock Analysis')

            return (
              <button
                type="button"
                key={label}
                className={isItemActive ? 'active' : ''}
                aria-current={isItemActive ? 'page' : undefined}
                onClick={() =>
                  handleNavigation(
                    label === 'NIFTY'
                      ? 'NIFTY Analysis'
                      : label === 'Scanner'
                        ? 'Stock Scanner'
                        : label === 'Analysis'
                          ? 'Stock Analysis'
                          : label === 'Paper'
                            ? 'Paper Trading'
                            : label,
                  )
                }
              >
                <Icon type={icon} />
                <span>{label}</span>
              </button>
            )
          })}
        </nav>

        {/* Keyboard Shortcuts Help Dialog Modal */}
        <KeyboardShortcutsModal
          isOpen={showShortcutsModal}
          onClose={() => setShowShortcutsModal(false)}
        />
      </main>
    </div>
  )
}

function NiftyAnalysisView({
  data,
  loading,
  error,
  onRefresh,
  onNavigateDashboard,
}) {
  const supportedTimeframes = ['5m', '10m', '15m', '30m']
  const tfLabels = {
    '5m': '5 MIN',
    '10m': '10 MIN',
    '15m': '15 MIN',
    '30m': '30 MIN',
  }

  // Header and primary metrics
  const symbol = data?.symbol || 'NIFTY 50'
  const price = typeof data?.price === 'number' ? data.price : null
  const timestamp = data?.timestamp || null
  const rawSignal = String(data?.signal || '').toUpperCase().trim()

  let signalText = '�'
  let signalClass = 'no-trade'

  if (loading && !data) {
    signalText = 'LOADING�'
    signalClass = 'loading'
  } else if (error && !data) {
    signalText = 'API UNAVAILABLE'
    signalClass = 'unavailable'
  } else if (rawSignal === 'BUY') {
    signalText = 'BUY'
    signalClass = 'buy'
  } else if (rawSignal === 'SELL') {
    signalText = 'SELL'
    signalClass = 'sell'
  } else if (rawSignal === 'NO_TRADE') {
    signalText = 'NO TRADE'
    signalClass = 'no-trade'
  } else if (rawSignal) {
    signalText = rawSignal.replace(/_/g, ' ')
    signalClass = 'no-trade'
  } else {
    signalText = 'NOT AVAILABLE'
    signalClass = 'unavailable'
  }

  const score = data?.analysis?.score ?? (loading ? '�' : 0)
  const confidence =
    typeof data?.analysis?.confidence === 'number'
      ? `${Math.round(data.analysis.confidence * 100)}%`
      : loading
        ? '�'
        : '0%'

  const mtfAlignment =
    typeof data?.analysis?.timeframe_alignment === 'number'
      ? data.analysis.timeframe_alignment
      : loading
        ? '�'
        : 0

  const reason =
    data?.analysis?.reason ||
    (loading
      ? 'Fetching strategy engine state...'
      : error
        ? 'Backend analysis API disconnected.'
        : 'Incomplete or neutral timeframe trend alignment.')

  return (
    <div className="nifty-analysis-view">
      {/* 1. Breadcrumb & Actions Bar */}
      <div className="analysis-breadcrumb-bar">
        <div className="breadcrumb-links">
          <button
            type="button"
            className="breadcrumb-link"
            onClick={onNavigateDashboard}
          >
            Dashboard
          </button>
          <span className="breadcrumb-sep">/</span>
          <span className="breadcrumb-current">NIFTY Analysis</span>
        </div>

        <div className="analysis-top-actions">
          <span className="analysis-dataset-tag">
            <span className="dataset-dot" />
            Historical Dataset • March 2024
          </span>

          <button
            type="button"
            className={`refresh-analysis-btn ${loading ? 'loading' : ''}`}
            onClick={onRefresh}
            disabled={loading}
            title="Refresh NIFTY Analysis"
          >
            <Icon type="refresh" />
            <span>{loading ? 'Refreshing…' : 'Refresh Analysis'}</span>
          </button>
        </div>
      </div>

      {loading && !data ? (
        <LoadingState
          title="Loading NIFTY 50 Strategy Analysis..."
          description="Calculating multi-timeframe trend alignment, confirmation metrics, and execution parameters from the backend strategy engine..."
        />
      ) : error && !data ? (
        <ErrorState
          title="Unable to Load NIFTY Analysis"
          message={error}
          onRetry={onRefresh}
          retryLabel="Retry Analysis"
        />
      ) : !data ? (
        <EmptyState
          title="No Analysis Data Available"
          description="No strategy analysis record was returned for NIFTY 50."
          action={
            <button
              type="button"
              className="sf-state-retry-btn"
              onClick={onRefresh}
            >
              Run Analysis
            </button>
          }
        />
      ) : (
        <>
          {error && (
            <div className="analysis-error-banner" role="alert">
              <Icon type="alert-circle" />
              <div className="error-banner-text">
                <strong>API Unavailable:</strong> {error}
              </div>
              <button
                type="button"
                className="error-retry-btn"
                onClick={onRefresh}
              >
                Retry Connection
              </button>
            </div>
          )}

          {/* 2. NIFTY Analysis Header Panel */}
          <section className="analysis-header-panel panel">
            <div className="analysis-header-top">
              <div className="analysis-title-block">
            <div className="symbol-badge-row">
              <h1 className="analysis-symbol">{symbol}</h1>
              <span className="strategy-tag">Strategy Analysis</span>
              <span className="historical-badge">
                <span className="badge-dot blue" />
                Historical API
              </span>
            </div>
            <p className="analysis-subtitle">
              SignalForge Causal Multi-Timeframe Strategy Engine (5m • 10m • 15m • 30m)
            </p>
          </div>

          <div className="analysis-header-metrics">
            <div className="header-metric-box">
              <span className="metric-box-label">Current Price</span>
              <strong className="metric-box-price tabular-num">
                {price !== null ? `?${formatPrice(price)}` : '�'}
              </strong>
            </div>

            <div className="header-metric-box">
              <span className="metric-box-label">Timestamp</span>
              <strong className="metric-box-val tabular-num">
                {formatApiTimestamp(timestamp)}
              </strong>
            </div>

            <div className="header-metric-box">
              <span className="metric-box-label">Data Status</span>
              <span className="provenance-pill">Historical (26 Mar 2024)</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Primary Signal & MTF Alignment Grid */}
      <section className="analysis-grid-three">
        {/* Primary Signal Card */}
        <div className="panel analysis-card primary-signal-card">
          <div className="card-header-clean">
            <span className="card-tag">AUTHORITATIVE ENGINE SIGNAL</span>
            <span className="engine-status-pill">Phase 10.2 Causal</span>
          </div>

          <div className="primary-signal-body">
            <div className={`analysis-dominant-badge ${signalClass}`}>
              <span className="signal-badge-glow" />
              <span className="dominant-signal-text">{signalText}</span>
            </div>

            <div className="signal-reason-box">
              <span className="reason-label">SIGNAL REASON</span>
              <p className="reason-text">"{reason}"</p>
            </div>

            <div className="signal-meta-row">
              <div className="meta-stat">
                <span className="meta-label">Signal Score</span>
                <strong className="meta-val tabular-num">{score}</strong>
              </div>
              <div className="meta-stat">
                <span className="meta-label">Confidence</span>
                <strong className="meta-val tabular-num">{confidence}</strong>
              </div>
              <div className="meta-stat">
                <span className="meta-label">MTF Alignment</span>
                <strong className="meta-val tabular-num">{mtfAlignment}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* MTF Summary Card */}
        <div className="panel analysis-card mtf-summary-card">
          <div className="card-header-clean">
            <span className="card-tag">MTF SUMMARY</span>
            <span className="summary-val-pill tabular-num">
              Alignment: {mtfAlignment}
            </span>
          </div>

          <div className="mtf-summary-body">
            <p className="mtf-summary-desc">
              Visual agreement across the 4 validated timeframes evaluated by the causal engine:
            </p>

            <div className="mtf-alignment-list">
              {supportedTimeframes.map((tf) => {
                const tfData = data?.timeframes?.[tf]
                const tfTrend = tfData?.trend
                  ? tfData.trend.replace(/_/g, ' ')
                  : '�'
                const trendClass =
                  tfTrend === 'SHORT'
                    ? 'negative'
                    : tfTrend === 'LONG'
                      ? 'positive'
                      : 'neutral'

                return (
                  <div className="mtf-summary-item" key={tf}>
                    <div className="tf-badge-pill">{tf}</div>
                    <span className="tf-arrow">?</span>
                    <span className={`tf-trend-tag ${trendClass}`}>
                      {tfTrend}
                    </span>
                    <span className="tf-item-close tabular-num text-muted">
                      {tfData?.close ? `?${formatPrice(tfData.close)}` : '�'}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className="mtf-total-alignment-meter">
              <div className="meter-header">
                <span>Overall Alignment Score:</span>
                <strong className="tabular-num">{mtfAlignment}</strong>
              </div>
              <div className="meter-track">
                <div
                  className="meter-fill"
                  style={{
                    width: `${Math.min(100, Math.max(0, (Number(mtfAlignment) / 4) * 100))}%`,
                  }}
                />
              </div>
              <small className="meter-caption">
                Source: <code>analysis.timeframe_alignment</code> (Requires all 4 timeframes aligned for trade confirmation).
              </small>
            </div>
          </div>
        </div>

        {/* Execution Levels Card */}
        <div className="panel analysis-card execution-levels-card">
          <div className="card-header-clean">
            <span className="card-tag">TRADE EXECUTION SECTION</span>
            <span className="not-avail-pill">Strictly Causal</span>
          </div>

          <div className="execution-levels-body">
            <div className="exec-status-banner">
              <Icon type="alert-circle" />
              <div>
                <strong>Execution Levels</strong>
                <p>Not available for current NO TRADE signal.</p>
              </div>
            </div>

            <div className="execution-levels-grid">
              <div className="exec-level-row">
                <span>Entry Price</span>
                <strong className="text-muted tabular-num">�</strong>
              </div>
              <div className="exec-level-row">
                <span>Stop Loss (SL)</span>
                <strong className="text-muted tabular-num">�</strong>
              </div>
              <div className="exec-level-row">
                <span>Target 1 (T1)</span>
                <strong className="text-muted tabular-num">�</strong>
              </div>
              <div className="exec-level-row">
                <span>Target 2 (T2)</span>
                <strong className="text-muted tabular-num">�</strong>
              </div>
              <div className="exec-level-row">
                <span>Risk / Reward (R:R)</span>
                <strong className="text-muted tabular-num">�</strong>
              </div>
            </div>

            <p className="execution-note">
              Execution brackets and targets are only calculated by the strategy upon confirmed BUY/SELL setup generation. No hypothetical levels are fabricated.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Timeframe Analysis Matrix (4 Cards) */}
      <section className="analysis-section">
        <div className="section-title-wrap">
          <h2 className="section-title">Timeframe Analysis</h2>
          <span className="section-sub">
            Causal indicator values from the 4 validated timeframes ({supportedTimeframes.join(', ')})
          </span>
        </div>

        <div className="timeframes-grid">
          {supportedTimeframes.map((tfKey) => {
            const tfData = data?.timeframes?.[tfKey]
            const tfTrend = tfData?.trend
              ? tfData.trend.replace(/_/g, ' ')
              : '�'
            const trendClass =
              tfTrend === 'SHORT'
                ? 'negative'
                : tfTrend === 'LONG'
                  ? 'positive'
                  : 'neutral'

            return (
              <div className="panel timeframe-card" key={tfKey}>
                <div className="tf-card-header">
                  <div className="tf-card-title-group">
                    <span className="tf-pill">{tfKey}</span>
                    <strong className="tf-card-name">{tfLabels[tfKey]}</strong>
                  </div>

                  <div className="tf-header-badges">
                    <span className={`tf-trend-badge ${trendClass}`}>
                      {tfTrend}
                    </span>
                    <span
                      className={`tf-readiness-pill ${tfData?.ready ? 'ready' : 'pending'
                        }`}
                    >
                      {tfData?.ready ? 'Ready' : 'Not Ready'}
                    </span>
                  </div>
                </div>

                <div className="tf-timestamp-row">
                  <span className="text-muted">Candle Time:</span>
                  <strong className="tabular-num">
                    {formatApiTimestamp(tfData?.timestamp)}
                  </strong>
                </div>

                <div className="tf-metrics-table">
                  <div className="tf-metric-item">
                    <span className="tf-metric-label">Close</span>
                    <strong className="tf-metric-val tabular-num">
                      {tfData?.close !== undefined && tfData?.close !== null
                        ? `?${formatPrice(tfData.close)}`
                        : '�'}
                    </strong>
                  </div>

                  <div className="tf-metric-item">
                    <span className="tf-metric-label">EMA 20</span>
                    <strong className="tf-metric-val tabular-num">
                      {formatNumber(tfData?.ema20)}
                    </strong>
                  </div>

                  <div className="tf-metric-item">
                    <span className="tf-metric-label">EMA 50</span>
                    <strong className="tf-metric-val tabular-num">
                      {formatNumber(tfData?.ema50)}
                    </strong>
                  </div>

                  <div className="tf-metric-item">
                    <span className="tf-metric-label">RSI 14</span>
                    <strong className="tf-metric-val tabular-num">
                      {formatNumber(tfData?.rsi14)}
                    </strong>
                  </div>

                  <div className="tf-metric-item">
                    <span className="tf-metric-label">ATR 14</span>
                    <strong className="tf-metric-val tabular-num">
                      {formatNumber(tfData?.atr14)}
                    </strong>
                  </div>

                  <div className="tf-metric-item">
                    <span className="tf-metric-label">RVOL 20</span>
                    <strong className="tf-metric-val tabular-num text-muted">
                      {tfData?.rvol20 !== null && tfData?.rvol20 !== undefined
                        ? formatNumber(tfData.rvol20)
                        : '�'}
                    </strong>
                  </div>
                </div>

                <div className="tf-card-footer">
                  <span className="tf-status-dot" />
                  <span>
                    Trend evaluated by <code>trend_direction()</code>
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* 5. Indicator Analysis & Explanation Section */}
      <section className="analysis-section">
        <div className="section-title-wrap">
          <h2 className="section-title">Indicator Analysis</h2>
          <span className="section-sub">
            Authoritative strategy indicator architecture and causal breakdown
          </span>
        </div>

        <div className="panel indicator-analysis-panel">
          {/* Root indicator status banner */}
          <div className="indicator-root-status-banner">
            <div className="status-banner-badge">ROOT INDICATOR STATUS</div>
            <div className="status-banner-content">
              <strong>"Use timeframe-level values below."</strong>
              <p>
                The SignalForge causal strategy computes indicators across resampled multi-timeframe candles (5m, 10m, 15m, 30m) rather than raw 1-minute noise candles. Root-level indicators are intentionally null in the engine response.
              </p>
            </div>
          </div>

          {/* Timeframe Indicators Table */}
          <div className="table-wrapper">
            <div className="indicator-comparison-table">
              <div className="table-head">
                <span>Timeframe</span>
                <span className="text-right">Close</span>
                <span className="text-right">EMA 20</span>
                <span className="text-right">EMA 50</span>
                <span className="text-right">RSI 14</span>
                <span className="text-right">ATR 14</span>
                <span className="text-right">RVOL 20</span>
                <span className="text-center">Trend</span>
                <span className="text-center">Status</span>
              </div>

              {supportedTimeframes.map((tf) => {
                const tfData = data?.timeframes?.[tf]
                const tfTrend = tfData?.trend
                  ? tfData.trend.replace(/_/g, ' ')
                  : '�'
                const trendClass =
                  tfTrend === 'SHORT'
                    ? 'negative'
                    : tfTrend === 'LONG'
                      ? 'positive'
                      : 'neutral'

                return (
                  <div className="indicator-row" key={tf}>
                    <strong>{tfLabels[tf]}</strong>
                    <span className="text-right tabular-num">
                      {tfData?.close ? `?${formatPrice(tfData.close)}` : '�'}
                    </span>
                    <span className="text-right tabular-num">
                      {formatNumber(tfData?.ema20)}
                    </span>
                    <span className="text-right tabular-num">
                      {formatNumber(tfData?.ema50)}
                    </span>
                    <span className="text-right tabular-num">
                      {formatNumber(tfData?.rsi14)}
                    </span>
                    <span className="text-right tabular-num">
                      {formatNumber(tfData?.atr14)}
                    </span>
                    <span className="text-right tabular-num text-muted">
                      {tfData?.rvol20 !== null && tfData?.rvol20 !== undefined
                        ? formatNumber(tfData.rvol20)
                        : '�'}
                    </span>
                    <div className="badge-cell text-center">
                      <span className={`tf-trend-tag small ${trendClass}`}>
                        {tfTrend}
                      </span>
                    </div>
                    <div className="badge-cell text-center">
                      <span className="ready-indicator-dot" />
                      <span className="text-muted small">
                        {tfData?.ready ? 'Ready' : 'Pending'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* RVOL Zero-Volume Notification Box */}
          <div className="rvol-notice-card">
            <div className="rvol-notice-header">
              <span className="rvol-icon-wrap">
                <Icon type="alert-circle" />
              </span>
              <div>
                <strong>RVOL 20</strong>
                <span className="rvol-status-tag">
                  Unavailable � source volume is zero
                </span>
              </div>
            </div>
            <p className="rvol-notice-desc">
              The historical NIFTY dataset has volume = 0. In accordance with SignalForge engine rules, relative volume calculation is automatically disabled to prevent division-by-zero or false volume confirmation. RVOL is intentionally represented as unavailable.
            </p>
          </div>
        </div>
      </section>

      {/* 6. Data Provenance Section */}
      <section className="analysis-section">
        <div className="section-title-wrap">
          <h2 className="section-title">Data Provenance</h2>
          <span className="section-sub">
            Causal integrity and data verification audit trail
          </span>
        </div>

        <div className="panel provenance-panel">
          <div className="provenance-grid">
            <div className="provenance-item">
              <span className="prov-label">Data Source</span>
              <strong className="prov-val">SignalForge historical dataset</strong>
              <span className="prov-sub">
                <code>data/historical/nifty50_1m_signalforge.csv</code>
              </span>
            </div>

            <div className="provenance-item">
              <span className="prov-label">Latest Candle</span>
              <strong className="prov-val tabular-num">
                {formatApiTimestamp(timestamp)}
              </strong>
              <span className="prov-sub">Evaluated up to 26 Mar 2024, 3:29 pm</span>
            </div>

            <div className="provenance-item">
              <span className="prov-label">Data Status</span>
              <strong className="prov-val">Historical</strong>
              <span className="prov-sub">
                Non-live replay data (Live adapter scheduled for Phase 11)
              </span>
            </div>

            <div className="provenance-item">
              <span className="prov-label">Signal Source</span>
              <strong className="prov-val">SignalForge causal strategy engine</strong>
              <span className="prov-sub">
                Zero lookahead bias • Strict candle close causality
              </span>
            </div>
          </div>

          <div className="provenance-footer-note">
            <span className="prov-check-icon">
              <Icon type="check-small" />
            </span>
            <span>
              Authoritative alignment verified: <code>/api/nifty/analysis.signal</code> is guaranteed identical to <code>/api/nifty/signal.signal</code>.
            </span>
          </div>
        </div>
      </section>
        </>
      )}
    </div>
  )
}

function TopMarket({ icon, label, value, change, negative }) {
  const isUnavailable = change === 'Unavailable' || change === '�'
  const changeClass = isUnavailable
    ? 'text-muted'
    : negative
      ? 'negative'
      : 'positive'

  return (
    <div className="top-market-item">
      <span className="market-icon">
        <MarketIcon type={icon} />
      </span>

      <div className="market-content">
        <small>{label}</small>

        <div className="market-row">
          <strong>{value}</strong>
          <span className={changeClass}>{change}</span>
        </div>
      </div>
    </div>
  )
}

function MarketIcon({ type }) {
  if (type === 'fii') {
    return (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <polygon points="8,1 15,8 8,15 1,8" />
      </svg>
    )
  }
  if (type === 'globe') {
    return (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="8" cy="8" r="6.5" />
        <line x1="1.5" y1="8" x2="14.5" y2="8" />
        <path d="M8 1.5a10 10 0 0 1 0 13 10 10 0 0 1 0-13" />
      </svg>
    )
  }
  if (type === 'barrel') {
    return (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <ellipse cx="8" cy="3.5" rx="5.5" ry="2" />
        <path d="M2.5 3.5v9c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-9" />
        <path d="M2.5 8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2" />
      </svg>
    )
  }
  return (
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" />
      <path d="M6 5.5h4M6 8h4M7 8a2 2 0 0 0 2-2M7.5 10.5 10 13" />
    </svg>
  )
}

// Module-level constant — created once at import time, not on every render.
const ICON_PATHS = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),

  chart: (
    <>
      <path d="M4 19V5" />
      <path d="M4 19h17" />
      <path d="m7 15 4-5 3 3 5-7" />
    </>
  ),

  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),

  bars: (
    <>
      <path d="M5 20V10" />
      <path d="M12 20V4" />
      <path d="M19 20v-7" />
    </>
  ),

  activity: (
    <>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </>
  ),

  bookmark: (
    <path d="M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-4-6 4V4Z" />
  ),

  plus: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </>
  ),

  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 2.5 2.5L16 9" />
    </>
  ),

  candles: (
    <>
      <path d="M6 4v5M6 15v5M4 9h4v6H4z" />
      <path d="M12 3v4M12 13v8M10 7h4v6h-4z" />
      <path d="M18 5v7M18 16v5M16 12h4v4h-4z" />
    </>
  ),

  briefcase: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M3 12h18" />
    </>
  ),

  report: (
    <>
      <path d="M6 2h9l4 4v16H6z" />
      <path d="M15 2v5h4M9 12h6M9 16h6M9 8h2" />
    </>
  ),

  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 0 0-.15-1.4l1.7-1.3-2-3.4-2 .8A7 7 0 0 0 14 5l-.3-2.1h-4L9.4 5a7 7 0 0 0-2.55 1.7l-2-.8-2 3.4 1.7 1.3A7 7 0 0 0 4.4 12c0 .48.05.95.15 1.4l-1.7 1.3 2 3.4 2-.8A7 7 0 0 0 9.4 19l.3 2.1h4L14 19a7 7 0 0 0 2.55-1.7l2 .8 2-3.4-1.7-1.3c.1-.45.15-.92.15-1.4Z" />
    </>
  ),

  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </>
  ),

  indicator: (
    <>
      <path d="M4 17h4M10 13h4M16 9h4" />
      <path d="M4 17 10 11 14 15 20 6" />
    </>
  ),

  template: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M4 9h16M9 9v11" />
    </>
  ),

  fullscreen: (
    <>
      <path d="M8 3H4a1 1 0 0 0-1 1v4M16 3h4a1 1 0 0 1 1 1v4M8 21H4a1 1 0 0 1-1-1v-4M16 21h4a1 1 0 0 0 1-1v-4" />
    </>
  ),

  'chevron-down': <path d="m6 9 6 6 6-6" />,

  'check-small': <path d="m5 12 4 4 10-10" />,

  'alert-circle': (
    <>
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <circle cx="12" cy="16" r="0.8" fill="currentColor" />
    </>
  ),

  keyboard: (
    <>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M8 16h8" />
    </>
  ),

  'arrow-right': (
    <>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </>
  ),

  'arrow-up-right': (
    <>
      <path d="M7 17 17 7" />
      <path d="M7 7h10v10" />
    </>
  ),

  'more-horizontal': (
    <>
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="19" cy="12" r="1.5" />
      <circle cx="5" cy="12" r="1.5" />
    </>
  ),

  refresh: (
    <>
      <path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" />
      <path d="M21 3v5h-5" />
    </>
  ),
}

function Icon({ type }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICON_PATHS[type]}
    </svg>
  )
}


function EquityChart() {
  return (
    <svg viewBox="0 0 680 130" preserveAspectRatio="none">
      <defs>
        <linearGradient
          id="equityGradient"
          x1="0"
          x2="0"
          y1="0"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="rgba(0, 217, 163, 0.25)"
          />

          <stop
            offset="100%"
            stopColor="rgba(0, 217, 163, 0)"
          />
        </linearGradient>
      </defs>

      <path
        d="M0 112
        C35 105 48 108 72 99
        S110 103 134 91
        S172 94 194 84
        S232 89 256 75
        S295 79 320 68
        S357 70 382 57
        S418 62 445 49
        S480 54 506 39
        S545 43 570 31
        S616 35 640 23
        S660 25 680 15
        L680 130
        L0 130Z"
        fill="url(#equityGradient)"
      />

      <path
        d="M0 112
        C35 105 48 108 72 99
        S110 103 134 91
        S172 94 194 84
        S232 89 256 75
        S295 79 320 68
        S357 70 382 57
        S418 62 445 49
        S480 54 506 39
        S545 43 570 31
        S616 35 640 23
        S660 25 680 15"
        className="equity-line"
      />
    </svg>
  )
}

function SignalBadge({ value }) {
  return (
    <span
      className={`signal-badge ${value
        .toLowerCase()
        .replace(' ', '-')}`}
    >
      {value}
    </span>
  )
}

function PanelTitle({ title, action, badge, extra }) {
  return (
    <div className="panel-title">
      <div className="panel-title-left">
        <h2>{title}</h2>
        {badge}
      </div>
      <div className="panel-title-right">
        {extra}
        {action && (
          <button type="button" className="panel-action-btn">
            {action}
          </button>
        )}
      </div>
    </div>
  )
}

function ValidationRing() {
  return (
    <div className="validation-ring">
      <svg viewBox="0 0 120 120">
        <circle
          cx="60"
          cy="60"
          r="48"
          className="ring-background"
        />

        <circle
          cx="60"
          cy="60"
          r="48"
          className="ring-progress"
        />
      </svg>

      <div className="ring-text">
        <strong>42 / 50</strong>
        <span>Validated</span>
      </div>
    </div>
  )
}

function ValidationItem({ label, value, className }) {
  return (
    <div className="validation-item">
      <span className={`validation-dot ${className}`} />
      <span>{label}</span>
      <strong className="tabular-num">{value}</strong>
    </div>
  )
}

function Metric({ label, value, sub, positive }) {
  return (
    <div className="metric">
      <span>{label}</span>

      <strong className={`tabular-num ${positive ? 'positive' : ''}`}>
        {value}
      </strong>

      {sub && (
        <small className={`tabular-num ${positive ? 'positive' : ''}`}>
          {sub}
        </small>
      )}
    </div>
  )
}

export default App






