/**
 * responsiveUtils.js — SignalForge Responsive Layout & UX Utilities
 *
 * Pure helper functions for layout calculations, breakpoint categorization,
 * touch target metrics, mobile navigation grids, and horizontal overflow checks.
 */

/**
 * Breakpoint thresholds in pixels matching SignalForge responsive architecture.
 */
export const BREAKPOINTS = Object.freeze({
  DESKTOP_XL: 1536,
  DESKTOP: 1440,
  LAPTOP: 1366,
  TABLET_LANDSCAPE: 1024,
  TABLET_PORTRAIT: 768,
  MOBILE_LARGE: 480,
  MOBILE_SMALL: 375,
})

/**
 * Categorize a viewport width into a standard SignalForge device breakpoint tier.
 * @param {number} width - Viewport width in pixels.
 * @returns {string} - 'desktop-xl' | 'desktop' | 'laptop' | 'tablet-landscape' | 'tablet-portrait' | 'mobile-large' | 'mobile-small'
 */
export function getResponsiveBreakpoint(width) {
  const w = Number(width)
  if (!Number.isFinite(w) || w <= 0) return 'mobile-small'

  if (w >= BREAKPOINTS.DESKTOP_XL) return 'desktop-xl'
  if (w >= BREAKPOINTS.DESKTOP) return 'desktop'
  if (w >= BREAKPOINTS.LAPTOP) return 'laptop'
  if (w >= BREAKPOINTS.TABLET_LANDSCAPE) return 'tablet-landscape'
  if (w >= BREAKPOINTS.TABLET_PORTRAIT) return 'tablet-portrait'
  if (w >= BREAKPOINTS.MOBILE_LARGE) return 'mobile-large'
  return 'mobile-small'
}

/**
 * Determine the number of top-header market data tickers to display to prevent clipping.
 * @param {number} viewportWidth - Viewport width in pixels.
 * @returns {number} - 0 to 4 visible tickers.
 */
export function calculateHeaderTickerVisibility(viewportWidth) {
  const w = Number(viewportWidth)
  if (!Number.isFinite(w) || w < 1024) return 0
  if (w < 1200) return 2 // Show 2 tickers (FII/DII, Global Markets)
  if (w < 1366) return 3 // Show 3 tickers (FII/DII, Global Markets, Crude Oil)
  return 4 // Show all 4 tickers on large screens
}

/**
 * Calculate mobile bottom navigation CSS grid columns string.
 * Ensures all items fit on a single row with comfortable touch targets.
 * @param {number} itemCount - Number of navigation items (e.g. 5 or 6).
 * @returns {string} - e.g. 'repeat(6, 1fr)'
 */
export function calculateMobileNavColumns(itemCount) {
  const count = Math.max(1, Math.floor(Number(itemCount) || 1))
  return `repeat(${count}, 1fr)`
}

/**
 * Compact formatting for stock symbol and name in space-constrained headers (e.g., mobile breadcrumbs).
 * @param {string} symbol - e.g. 'RELIANCE'
 * @param {string} name - e.g. 'Reliance Industries Limited'
 * @param {number} maxLength - Max characters for name (default 24).
 * @returns {string} - Formatted compact string.
 */
export function formatCompactStockName(symbol, name, maxLength = 24) {
  const cleanSymbol = String(symbol || '').trim().toUpperCase()
  if (!cleanSymbol) return ''

  const cleanName = String(name || '').trim()
  if (!cleanName || cleanName.toUpperCase() === cleanSymbol) {
    return cleanSymbol
  }

  if (cleanName.length <= maxLength) {
    return `${cleanSymbol} — ${cleanName}`
  }

  return `${cleanSymbol} — ${cleanName.slice(0, maxLength - 1)}…`
}

/**
 * Test whether page-level horizontal overflow exists.
 * Per project specification, PAGE HORIZONTAL OVERFLOW MUST BE ZERO.
 * @param {number} scrollWidth - document.documentElement.scrollWidth or document.body.scrollWidth.
 * @param {number} clientWidth - window.innerWidth or document.documentElement.clientWidth.
 * @returns {boolean} - True if page has horizontal overflow, false if clean.
 */
export function hasPageHorizontalOverflow(scrollWidth, clientWidth) {
  const sWidth = Math.max(0, Number(scrollWidth) || 0)
  const cWidth = Math.max(0, Number(clientWidth) || 0)
  // Allow 1px subpixel rounding tolerance in modern browser engines
  return sWidth > cWidth + 1
}

/**
 * Minimum recommended touch target size (44px) check.
 * @param {number} height - Interactive element height in pixels.
 * @param {number} [width] - Optional interactive element width in pixels.
 * @returns {boolean} - True if meets or exceeds touch target standards.
 */
export function isComfortableTouchTarget(height, width = 44) {
  const h = Number(height) || 0
  const w = Number(width) || 0
  return h >= 44 && w >= 44
}
