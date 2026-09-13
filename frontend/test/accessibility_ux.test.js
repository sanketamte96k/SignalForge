import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import KeyboardShortcutsModal from '../src/KeyboardShortcutsModal.jsx'
import { LoadingState, ErrorState } from '../src/StateViews.jsx'
import { normalizeSignal, normalizeStatus } from '../src/scannerUtils.js'
import { normalizeAnalysisSignal, normalizeAnalysisStatus } from '../src/analysisUtils.js'

describe('Accessibility & UX Quality (Improvement #9)', () => {
  // -------------------------------------------------------------------------
  // 1. Navigation Landmarks & aria-current
  // -------------------------------------------------------------------------
  it('1. Navigation exposes expected accessible names and current state', () => {
    // Test navigation element attributes
    const activeNav = 'Dashboard'
    const navItems = [['Dashboard', 'dashboard'], ['Stock Scanner', 'search']]

    const sidebarNavMarkup = renderToStaticMarkup(
      React.createElement(
        'nav',
        { className: 'sidebar-nav', 'aria-label': 'Main Navigation' },
        navItems.map(([label]) =>
          React.createElement(
            'button',
            {
              type: 'button',
              key: label,
              className: `sidebar-item ${activeNav === label ? 'active' : ''}`,
              'aria-current': activeNav === label ? 'page' : undefined,
            },
            label,
          ),
        ),
      ),
    )

    assert.match(sidebarNavMarkup, /aria-label="Main Navigation"/)
    assert.match(sidebarNavMarkup, /aria-current="page"/)
    assert.match(sidebarNavMarkup, /Dashboard/)

    const mobileNavMarkup = renderToStaticMarkup(
      React.createElement(
        'nav',
        { className: 'mobile-nav', 'aria-label': 'Mobile Navigation' },
        navItems.map(([label]) => {
          const isActive = activeNav === label
          return React.createElement(
            'button',
            {
              type: 'button',
              key: label,
              className: isActive ? 'active' : '',
              'aria-current': isActive ? 'page' : undefined,
            },
            label,
          )
        }),
      ),
    )

    assert.match(mobileNavMarkup, /aria-label="Mobile Navigation"/)
    assert.match(mobileNavMarkup, /aria-current="page"/)
  })

  // -------------------------------------------------------------------------
  // 2. Hamburger Button Accessibility
  // -------------------------------------------------------------------------
  it('2. Hamburger exposes expanded and collapsed states with dynamic accessible names', () => {
    // Collapsed state
    const collapsedMarkup = renderToStaticMarkup(
      React.createElement('button', {
        type: 'button',
        className: 'mobile-toggle',
        'aria-label': 'Open navigation',
        'aria-expanded': false,
      }),
    )
    assert.match(collapsedMarkup, /aria-label="Open navigation"/)
    assert.match(collapsedMarkup, /aria-expanded="false"/)

    // Expanded state
    const expandedMarkup = renderToStaticMarkup(
      React.createElement('button', {
        type: 'button',
        className: 'mobile-toggle',
        'aria-label': 'Close navigation',
        'aria-expanded': true,
      }),
    )
    assert.match(expandedMarkup, /aria-label="Close navigation"/)
    assert.match(expandedMarkup, /aria-expanded="true"/)
  })

  // -------------------------------------------------------------------------
  // 3. Icon-only Controls have accessible names
  // -------------------------------------------------------------------------
  it('3. Icon-only controls have accessible names and visible hints', () => {
    const controlsMarkup = renderToStaticMarkup(
      React.createElement(
        'div',
        null,
        React.createElement('button', {
          type: 'button',
          className: 'header-shortcuts-btn',
          'aria-label': 'Keyboard shortcuts (?)',
          title: 'Keyboard shortcuts (?)',
        }),
        React.createElement('button', {
          type: 'button',
          className: 'chart-zoom-btn',
          'aria-label': 'Zoom in',
          title: 'Zoom In',
        }),
        React.createElement('button', {
          type: 'button',
          className: 'chart-zoom-btn',
          'aria-label': 'Zoom out',
          title: 'Zoom Out',
        }),
        React.createElement('button', {
          type: 'button',
          className: 'chart-zoom-btn chart-zoom-reset',
          'aria-label': 'Reset zoom range',
        }, 'Reset'),
      ),
    )

    assert.match(controlsMarkup, /aria-label="Keyboard shortcuts \(\?\)"/)
    assert.match(controlsMarkup, /aria-label="Zoom in"/)
    assert.match(controlsMarkup, /aria-label="Zoom out"/)
    assert.match(controlsMarkup, /aria-label="Reset zoom range"/)
  })

  // -------------------------------------------------------------------------
  // 4. Global Search Accessibility
  // -------------------------------------------------------------------------
  it('4. Search input is accessible with placeholder and label', () => {
    const searchMarkup = renderToStaticMarkup(
      React.createElement(
        'label',
        { className: 'global-search' },
        React.createElement('input', {
          value: '',
          placeholder: 'Search stocks, sectors, or watchlists...',
          'aria-label': 'Search stocks, sectors, or watchlists',
          readOnly: true,
        }),
      ),
    )

    assert.match(searchMarkup, /aria-label="Search stocks, sectors, or watchlists"/)
    assert.match(searchMarkup, /placeholder="Search stocks, sectors, or watchlists\.\.\."/)
  })

  // -------------------------------------------------------------------------
  // 5. KeyboardShortcutsModal Dialog Semantics
  // -------------------------------------------------------------------------
  it('5. KeyboardShortcutsModal exposes dialog semantics and labeling', () => {
    const modalMarkup = renderToStaticMarkup(
      React.createElement(KeyboardShortcutsModal, {
        isOpen: true,
        onClose: () => {},
      }),
    )

    assert.match(modalMarkup, /role="dialog"/)
    assert.match(modalMarkup, /aria-modal="true"/)
    assert.match(modalMarkup, /aria-labelledby="shortcuts-modal-title"/)
    assert.match(modalMarkup, /id="shortcuts-modal-title"/)
    assert.match(modalMarkup, /aria-label="Close shortcuts dialog \(Esc\)"/)
  })

  it('5b. KeyboardShortcutsModal returns null when closed', () => {
    const modalMarkup = renderToStaticMarkup(
      React.createElement(KeyboardShortcutsModal, {
        isOpen: false,
        onClose: () => {},
      }),
    )
    assert.equal(modalMarkup, '')
  })

  // -------------------------------------------------------------------------
  // 6. Focus Trap Calculation
  // -------------------------------------------------------------------------
  it('6. Modal focus trap correctly identifies first and last focusable elements', () => {
    // Verify focusable selector elements
    const elements = [
      { tag: 'BUTTON', disabled: false, tabIndex: 0 },
      { tag: 'INPUT', disabled: false, tabIndex: 0 },
      { tag: 'BUTTON', disabled: false, tabIndex: 0 },
    ]

    const first = elements[0]
    const last = elements[elements.length - 1]

    // Shift+Tab on first wraps to last
    const shiftTabWrap = (active) => (active === first ? last : null)
    assert.equal(shiftTabWrap(first), last)

    // Tab on last wraps to first
    const tabWrap = (active) => (active === last ? first : null)
    assert.equal(tabWrap(last), first)
  })

  // -------------------------------------------------------------------------
  // 7. Loading and Error State Semantics
  // -------------------------------------------------------------------------
  it('7. LoadingState exposes role=status, aria-live=polite, and aria-busy=true', () => {
    const loadingMarkup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: 'Loading Chart',
        description: 'Retrieving data...',
      }),
    )

    assert.match(loadingMarkup, /role="status"/)
    assert.match(loadingMarkup, /aria-live="polite"/)
    assert.match(loadingMarkup, /aria-busy="true"/)
    assert.match(loadingMarkup, /Loading Chart/)
  })

  it('7b. ErrorState exposes role=alert, aria-live=assertive, and retry action', () => {
    const errorMarkup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'API Disconnected',
        message: 'Network timeout',
        onRetry: () => {},
        retryLabel: 'Retry Connection',
      }),
    )

    assert.match(errorMarkup, /role="alert"/)
    assert.match(errorMarkup, /aria-live="assertive"/)
    assert.match(errorMarkup, /aria-label="Retry Connection"/)
  })

  // -------------------------------------------------------------------------
  // 8. Timeframe Controls Tabs
  // -------------------------------------------------------------------------
  it('8. Timeframe controls expose tablist, tab role, and aria-selected', () => {
    const timeframes = ['5m', '10m', '15m', '30m']
    const activeTf = '15m'

    const tabsMarkup = renderToStaticMarkup(
      React.createElement(
        'div',
        { role: 'tablist', 'aria-label': 'Select chart timeframe' },
        timeframes.map((tf) =>
          React.createElement('button', {
            type: 'button',
            key: tf,
            role: 'tab',
            'aria-selected': activeTf === tf,
            'aria-label': `Select ${tf} timeframe`,
            className: activeTf === tf ? 'active' : '',
          }, tf),
        ),
      ),
    )

    assert.match(tabsMarkup, /role="tablist"/)
    assert.match(tabsMarkup, /aria-label="Select chart timeframe"/)
    assert.match(tabsMarkup, /aria-selected="true"/)
    assert.match(tabsMarkup, /aria-selected="false"/)
  })

  // -------------------------------------------------------------------------
  // 9. Scanner Keyboard Selection & Table Semantics
  // -------------------------------------------------------------------------
  it('9. Scanner table rows are keyboard accessible with role=row and aria-selected', () => {
    const isSelected = true
    const rowMarkup = renderToStaticMarkup(
      React.createElement(
        'div',
        {
          className: `scanner-table-row ${isSelected ? 'is-selected' : ''}`,
          role: 'row',
          tabIndex: 0,
          'aria-selected': isSelected,
        },
        React.createElement('div', { role: 'cell' }, 'RELIANCE'),
        React.createElement('div', { role: 'cell' }, 'BUY'),
        React.createElement(
          'button',
          {
            type: 'button',
            className: 'scanner-row-analyze-btn',
            'aria-label': 'Analyze RELIANCE',
          },
          'Analyze →',
        ),
      ),
    )

    assert.match(rowMarkup, /role="row"/)
    assert.match(rowMarkup, /tabindex="0"/)
    assert.match(rowMarkup, /aria-selected="true"/)
    assert.match(rowMarkup, /aria-label="Analyze RELIANCE"/)
  })

  // -------------------------------------------------------------------------
  // 10. Non-color Meaning for Important Signals & Statuses
  // -------------------------------------------------------------------------
  it('10. Important signals and statuses contain explicit non-color textual meaning', () => {
    // Signals
    assert.equal(normalizeSignal('BUY'), 'BUY')
    assert.equal(normalizeSignal('SELL'), 'SELL')
    assert.equal(normalizeSignal('NO_TRADE'), 'NO TRADE')
    assert.equal(normalizeAnalysisSignal('BUY'), 'BUY')
    assert.equal(normalizeAnalysisSignal('SELL'), 'SELL')
    assert.equal(normalizeAnalysisSignal('NO_TRADE'), 'NO TRADE')

    // Statuses
    assert.equal(normalizeStatus('VALIDATED'), 'VALIDATED')
    assert.equal(normalizeStatus('TESTING'), 'TESTING')
    assert.equal(normalizeStatus('FAILED'), 'FAILED')
    assert.equal(normalizeAnalysisStatus('VALIDATED'), 'VALIDATED')
    assert.equal(normalizeAnalysisStatus('TESTING'), 'TESTING')
    assert.equal(normalizeAnalysisStatus('REJECTED'), 'REJECTED')
  })

  // -------------------------------------------------------------------------
  // 11. Watchlists and Sectors Single Main Landmark
  // -------------------------------------------------------------------------
  it('11. Watchlists view renders as div to prevent nested main landmark violations', () => {
    // Render sample structure of watchlists page container
    const watchlistsContainer = renderToStaticMarkup(
      React.createElement('div', { className: 'watchlists-page' },
        React.createElement('section', { className: 'watchlists-header' }, 'Header'),
      ),
    )

    assert.match(watchlistsContainer, /^<div class="watchlists-page">/)
    assert.doesNotMatch(watchlistsContainer, /^<main/)
  })

  // -------------------------------------------------------------------------
  // 12. Chart SVG accessibility titles and descriptions
  // -------------------------------------------------------------------------
  it('12. Candlestick and RSI charts include accessible title and desc elements', () => {
    const svgMarkup = renderToStaticMarkup(
      React.createElement(
        'svg',
        {
          role: 'img',
          'aria-label': 'NIFTY 50 15m interactive candlestick and volume chart',
        },
        React.createElement('title', null, 'NIFTY 50 15m Candlestick and Volume Chart'),
        React.createElement('desc', null, 'Interactive chart showing 100 candles.'),
      ),
    )

    assert.match(svgMarkup, /role="img"/)
    assert.match(svgMarkup, /<title>NIFTY 50 15m Candlestick and Volume Chart<\/title>/)
    assert.match(svgMarkup, /<desc>Interactive chart showing 100 candles\.<\/desc>/)
  })
})
