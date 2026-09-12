import test from 'node:test'
import assert from 'node:assert/strict'
import {
  BREAKPOINTS,
  getResponsiveBreakpoint,
  calculateHeaderTickerVisibility,
  calculateMobileNavColumns,
  formatCompactStockName,
  hasPageHorizontalOverflow,
  isComfortableTouchTarget,
} from '../src/responsiveUtils.js'

test('Responsive & Layout Polish (Improvement #5)', async (t) => {
  await t.test('1. Categorizes viewports into correct responsive breakpoint tiers', () => {
    assert.equal(getResponsiveBreakpoint(1600), 'desktop-xl')
    assert.equal(getResponsiveBreakpoint(1536), 'desktop-xl')
    assert.equal(getResponsiveBreakpoint(1440), 'desktop')
    assert.equal(getResponsiveBreakpoint(1366), 'laptop')
    assert.equal(getResponsiveBreakpoint(1200), 'tablet-landscape')
    assert.equal(getResponsiveBreakpoint(1024), 'tablet-landscape')
    assert.equal(getResponsiveBreakpoint(860), 'tablet-portrait')
    assert.equal(getResponsiveBreakpoint(768), 'tablet-portrait')
    assert.equal(getResponsiveBreakpoint(600), 'mobile-large')
    assert.equal(getResponsiveBreakpoint(480), 'mobile-large')
    assert.equal(getResponsiveBreakpoint(375), 'mobile-small')
    assert.equal(getResponsiveBreakpoint(320), 'mobile-small')
    assert.equal(getResponsiveBreakpoint(-10), 'mobile-small')
  })

  await t.test('2. Calculates progressive header ticker visibility across breakpoints', () => {
    assert.equal(calculateHeaderTickerVisibility(1536), 4)
    assert.equal(calculateHeaderTickerVisibility(1440), 4)
    assert.equal(calculateHeaderTickerVisibility(1366), 4)
    assert.equal(calculateHeaderTickerVisibility(1300), 3)
    assert.equal(calculateHeaderTickerVisibility(1180), 2)
    assert.equal(calculateHeaderTickerVisibility(1024), 2)
    assert.equal(calculateHeaderTickerVisibility(900), 0)
    assert.equal(calculateHeaderTickerVisibility(768), 0)
    assert.equal(calculateHeaderTickerVisibility(375), 0)
  })

  await t.test('3. Generates correct CSS grid columns for mobile bottom nav', () => {
    assert.equal(calculateMobileNavColumns(5), 'repeat(5, 1fr)')
    assert.equal(calculateMobileNavColumns(6), 'repeat(6, 1fr)')
    assert.equal(calculateMobileNavColumns(4), 'repeat(4, 1fr)')
    assert.equal(calculateMobileNavColumns(0), 'repeat(1, 1fr)')
  })

  await t.test('4. Formats compact stock names for space-constrained mobile breadcrumbs', () => {
    assert.equal(formatCompactStockName('TCS', 'Tata Consultancy Services Limited', 16), 'TCS — Tata Consultanc…')
    assert.equal(formatCompactStockName('RELIANCE', 'Reliance Industries Ltd', 30), 'RELIANCE — Reliance Industries Ltd')
    assert.equal(formatCompactStockName('INFY', 'INFY'), 'INFY')
    assert.equal(formatCompactStockName('HDFCBANK', ''), 'HDFCBANK')
    assert.equal(formatCompactStockName('', 'Tata Steel'), '')
  })

  await t.test('5. Validates page-level horizontal overflow detection with subpixel tolerance', () => {
    // Zero overflow
    assert.equal(hasPageHorizontalOverflow(375, 375), false)
    assert.equal(hasPageHorizontalOverflow(768, 768), false)
    assert.equal(hasPageHorizontalOverflow(1440, 1440), false)

    // Subpixel rounding within 1px is safe
    assert.equal(hasPageHorizontalOverflow(375.8, 375), false)

    // Actual page horizontal overflow
    assert.equal(hasPageHorizontalOverflow(410, 375), true)
    assert.equal(hasPageHorizontalOverflow(800, 768), true)
    assert.equal(hasPageHorizontalOverflow(1500, 1440), true)
  })

  await t.test('6. Evaluates touch target dimensions for mobile accessibility standards', () => {
    assert.equal(isComfortableTouchTarget(44, 44), true)
    assert.equal(isComfortableTouchTarget(48, 60), true)
    assert.equal(isComfortableTouchTarget(60, 60), true)

    // Sub-44px targets return false
    assert.equal(isComfortableTouchTarget(30, 44), false)
    assert.equal(isComfortableTouchTarget(44, 30), false)
    assert.equal(isComfortableTouchTarget(22, 22), false)
  })

  await t.test('7. Frozen breakpoint constants match project specifications', () => {
    assert.equal(BREAKPOINTS.DESKTOP_XL, 1536)
    assert.equal(BREAKPOINTS.DESKTOP, 1440)
    assert.equal(BREAKPOINTS.LAPTOP, 1366)
    assert.equal(BREAKPOINTS.TABLET_LANDSCAPE, 1024)
    assert.equal(BREAKPOINTS.TABLET_PORTRAIT, 768)
    assert.equal(BREAKPOINTS.MOBILE_LARGE, 480)
    assert.equal(BREAKPOINTS.MOBILE_SMALL, 375)
  })
})
