import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ToastContext } from '../src/useToast.js'
import SettingsView from '../src/SettingsView.jsx'
import {
  DEFAULT_SETTINGS,
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
} from '../src/settingsUtils.js'

describe('SignalForge Settings UX & Preferences', () => {
  const mockToast = {
    success: () => {},
    error: () => {},
    warning: () => {},
    info: () => {},
  }

  function renderSettings() {
    return renderToStaticMarkup(
      React.createElement(
        ToastContext.Provider,
        { value: mockToast },
        React.createElement(SettingsView, null),
      ),
    )
  }

  // -------------------------------------------------------------------------
  // 1. Settings Schema & Defaults
  // -------------------------------------------------------------------------
  it('1. DEFAULT_SETTINGS contains all required preferences across 5 core preference groups', () => {
    // 1. General
    assert.equal(DEFAULT_SETTINGS.defaultTimeframe, '15m')
    assert.equal(DEFAULT_SETTINGS.autoRefresh, true)
    assert.equal(DEFAULT_SETTINGS.autoRefreshInterval, '30s')
    assert.equal(DEFAULT_SETTINGS.defaultLandingView, 'Dashboard')

    // 2. Chart Preferences
    assert.equal(DEFAULT_SETTINGS.showEma, true)
    assert.equal(DEFAULT_SETTINGS.showVolume, true)
    assert.equal(DEFAULT_SETTINGS.showRsi, true)
    assert.equal(DEFAULT_SETTINGS.crosshair, 'Normal')
    assert.equal(DEFAULT_SETTINGS.defaultChartType, 'Candlestick')

    // 3. Notifications
    assert.equal(DEFAULT_SETTINGS.tradingSignalNotifications, true)
    assert.equal(DEFAULT_SETTINGS.validationWarnings, true)
    assert.equal(DEFAULT_SETTINGS.toastNotifications, true)

    // 4. Trading Preferences
    assert.equal(DEFAULT_SETTINGS.riskPerTrade, '1.0%')
    assert.equal(DEFAULT_SETTINGS.defaultPositionSize, 50000)
    assert.equal(DEFAULT_SETTINGS.brokerageSlippage, '0.05%')

    // 5. Interface
    assert.equal(DEFAULT_SETTINGS.compactInterface, false)
    assert.equal(DEFAULT_SETTINGS.sidebarBehavior, 'Expanded')
  })

  it('2. Standard preference options are comprehensively defined', () => {
    assert.ok(TIMEFRAME_OPTIONS.includes('15m'))
    assert.ok(TIMEFRAME_OPTIONS.includes('1D'))
    assert.equal(REFRESH_INTERVAL_OPTIONS.length >= 4, true)
    assert.ok(LANDING_VIEW_OPTIONS.includes('Dashboard'))
    assert.ok(LANDING_VIEW_OPTIONS.includes('Stock Scanner'))
    assert.ok(CHART_TYPE_OPTIONS.includes('Candlestick'))
    assert.ok(CHART_TYPE_OPTIONS.includes('Line'))
    assert.equal(CROSSHAIR_OPTIONS.length, 3)
    assert.ok(RISK_OPTIONS.includes('1.0%'))
    assert.equal(BROKERAGE_OPTIONS.length >= 3, true)
    assert.equal(SIDEBAR_BEHAVIOR_OPTIONS.length, 3)
  })

  // -------------------------------------------------------------------------
  // 2. Storage Helpers
  // -------------------------------------------------------------------------
  it('3. loadSettings handles missing or mock storage gracefully', () => {
    // Mock global window and localStorage
    const originalWindow = global.window
    global.window = {
      localStorage: {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
      },
    }

    const loaded = loadSettings()
    assert.deepEqual(loaded, DEFAULT_SETTINGS)

    // Corrupt JSON handling
    global.window.localStorage.getItem = () => '{ invalid json }'
    const fallback = loadSettings()
    assert.deepEqual(fallback, DEFAULT_SETTINGS)

    // Saved override merge
    global.window.localStorage.getItem = () =>
      JSON.stringify({ defaultTimeframe: '5m', compactInterface: true })
    const merged = loadSettings()
    assert.equal(merged.defaultTimeframe, '5m')
    assert.equal(merged.compactInterface, true)
    assert.equal(merged.autoRefresh, true) // Preserved default

    global.window = originalWindow
  })

  it('4. saveSettings persists merged state and resetSettings restores factory defaults', () => {
    const store = {}
    const originalWindow = global.window
    global.window = {
      localStorage: {
        getItem: (k) => store[k] ?? null,
        setItem: (k, v) => {
          store[k] = String(v)
        },
        removeItem: (k) => {
          delete store[k]
        },
      },
    }

    const savedSuccess = saveSettings({ riskPerTrade: '2.0%', defaultPositionSize: 100000 })
    assert.equal(savedSuccess, true)
    assert.ok(store['signalforge_settings'])
    assert.match(store['signalforge_settings'], /"riskPerTrade":"2\.0%"/)
    assert.match(store['signalforge_settings'], /"defaultPositionSize":100000/)

    const resetDefaults = resetSettings()
    assert.equal(store['signalforge_settings'], undefined)
    assert.equal(resetDefaults.riskPerTrade, '1.0%')
    assert.equal(resetDefaults.defaultPositionSize, 50000)

    global.window = originalWindow
  })

  it('5. applySettingsToDOM updates density attributes and body class', () => {
    const originalDoc = global.document
    let attrKey = ''
    let attrVal = ''
    const classes = new Set()

    global.document = {
      documentElement: {
        setAttribute: (k, v) => {
          attrKey = k
          attrVal = v
        },
      },
      body: {
        classList: {
          add: (cls) => classes.add(cls),
          remove: (cls) => classes.delete(cls),
        },
      },
    }

    applySettingsToDOM({ compactInterface: true })
    assert.equal(attrKey, 'data-density')
    assert.equal(attrVal, 'compact')
    assert.ok(classes.has('sf-compact'))

    applySettingsToDOM({ compactInterface: false })
    assert.equal(attrVal, 'comfortable')
    assert.ok(!classes.has('sf-compact'))

    global.document = originalDoc
  })

  // -------------------------------------------------------------------------
  // 3. SettingsView Markup & Sections
  // -------------------------------------------------------------------------
  it('6. SettingsView renders as a container div without nested main landmark violations', () => {
    const markup = renderSettings()
    assert.match(markup, /^<div class="settings-view" role="region" aria-label="Terminal Settings">/)
    assert.doesNotMatch(markup, /^<main/)
  })

  it('7. SettingsView renders all 7 requested section headings', () => {
    const markup = renderSettings()
    assert.match(markup, /1\.\s*General/)
    assert.match(markup, /2\.\s*Chart Preferences/)
    assert.match(markup, /3\.\s*Notifications/)
    assert.match(markup, /4\.\s*Trading Preferences/)
    assert.match(markup, /5\.\s*Interface/)
    assert.match(markup, /6\.\s*Data &amp; API/)
    assert.match(markup, /7\.\s*Reset/)
  })

  it('8. General section renders timeframe buttons, auto refresh toggle, and landing view select', () => {
    const markup = renderSettings()
    assert.match(markup, /Default Timeframe/)
    assert.match(markup, /Auto Refresh/)
    assert.match(markup, /Default Landing View/)
    assert.match(markup, /role="radiogroup" aria-label="Default Timeframe"/)
    assert.match(markup, /aria-label="Toggle auto refresh"/)
    assert.match(markup, /id="setting-default-landing-view"/)
  })

  it('9. Chart preferences section renders EMA, Volume, RSI, Crosshair, and Chart Type controls', () => {
    const markup = renderSettings()
    assert.match(markup, /Show Exponential Moving Averages \(EMA\)/)
    assert.match(markup, /Show Volume Histogram/)
    assert.match(markup, /Show Relative Strength Index \(RSI 14\)/)
    assert.match(markup, /Crosshair Mode/)
    assert.match(markup, /Default Chart Type/)
    assert.match(markup, /aria-label="Toggle show EMA"/)
    assert.match(markup, /aria-label="Toggle show volume"/)
    assert.match(markup, /aria-label="Toggle show RSI"/)
    assert.match(markup, /role="radiogroup" aria-label="Crosshair mode"/)
    assert.match(markup, /role="radiogroup" aria-label="Default chart type"/)
  })

  it('10. Notifications section renders accessible toggles for signals, validation, and toast banners', () => {
    const markup = renderSettings()
    assert.match(markup, /Trading Signal Notifications/)
    assert.match(markup, /Validation Gate Warnings/)
    assert.match(markup, /In-Terminal Toast Notifications/)
    assert.match(markup, /aria-label="Toggle trading signal notifications"/)
    assert.match(markup, /aria-label="Toggle validation warnings"/)
    assert.match(markup, /aria-label="Toggle toast notifications"/)
  })

  it('11. Trading preferences section renders risk, position size, and brokerage options', () => {
    const markup = renderSettings()
    assert.match(markup, /Risk Per Trade/)
    assert.match(markup, /Default Position Size/)
    assert.match(markup, /Brokerage &amp; Slippage Assumption/)
    assert.match(markup, /id="setting-default-position-size"/)
    assert.match(markup, /id="setting-brokerage-slippage"/)
  })

  it('12. Interface section renders compact density toggle and sidebar behavior options', () => {
    const markup = renderSettings()
    assert.match(markup, /Compact Density Mode/)
    assert.match(markup, /Sidebar Behavior/)
    assert.match(markup, /aria-label="Toggle compact interface density"/)
    assert.match(markup, /role="radiogroup" aria-label="Sidebar behavior"/)
  })

  it('13. Data & API section clearly marks unavailable and not-configured services honestly', () => {
    const markup = renderSettings()
    // Local active services
    assert.match(markup, /Local Parquet Engine/)
    assert.match(markup, /Vectorized Indicator Engine/)
    assert.match(markup, /Paper Trading Simulator/)
    assert.match(markup, /● ACTIVE/)

    // Not configured broker services
    assert.match(markup, /Zerodha Kite Connect/)
    assert.match(markup, /Upstox Pro API/)
    assert.match(markup, /Angel One SmartAPI/)
    assert.match(markup, /WebSocket Tick Feed/)
    assert.match(markup, /○ NOT CONFIGURED/)

    // Unavailable external feeds
    assert.match(markup, /FII \/ DII Institutional Flow/)
    assert.match(markup, /✕ UNAVAILABLE/)
  })

  it('14. Reset section renders reset action button with danger styling and description', () => {
    const markup = renderSettings()
    assert.match(markup, /Reset All Terminal Preferences/)
    assert.match(markup, /aria-label="Open reset settings confirmation dialog"/)
    assert.match(markup, /Reset Defaults/)
  })
})
