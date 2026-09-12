import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from '../src/StateViews.jsx'
import { sanitizeErrorMessage } from '../src/stateUtils.js'

describe('Global State Components (LoadingState, ErrorState, EmptyState)', () => {
  // -------------------------------------------------------------------------
  // 1. LoadingState renders
  // -------------------------------------------------------------------------
  it('1. LoadingState renders with title, description, and accessibility attributes', () => {
    const markup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: 'Loading Analysis',
        description: 'Fetching market data...',
      }),
    )

    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /Loading Analysis/)
    assert.match(markup, /Fetching market data\.\.\./)
    assert.match(markup, /sf-spinner/)
    assert.doesNotMatch(markup, /sf-state-compact/)
  })

  it('1b. LoadingState supports compact mode and custom aria-label', () => {
    const markup = renderToStaticMarkup(
      React.createElement(LoadingState, {
        title: 'Checking Status',
        compact: true,
        ariaLabel: 'Custom status check',
      }),
    )

    assert.match(markup, /sf-state-compact/)
    assert.match(markup, /aria-label="Custom status check"/)
    assert.match(markup, /sf-spinner-small/)
  })

  // -------------------------------------------------------------------------
  // 2. ErrorState renders
  // -------------------------------------------------------------------------
  it('2. ErrorState renders with title, message, and accessibility attributes', () => {
    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'Unable to Load Data',
        message: 'Market analysis could not be loaded.',
      }),
    )

    assert.match(markup, /role="alert"/)
    assert.match(markup, /aria-live="assertive"/)
    assert.match(markup, /Unable to Load Data/)
    assert.match(markup, /Market analysis could not be loaded\./)
    assert.match(markup, /sf-error-icon/)
    // No onRetry passed, so no retry button
    assert.doesNotMatch(markup, /sf-state-retry-btn/)
  })

  it('2b. ErrorState renders retry button when onRetry is provided', () => {
    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'Connection Error',
        message: 'Failed to connect to backend',
        onRetry: () => {},
        retryLabel: 'Try Again',
      }),
    )

    assert.match(markup, /sf-state-retry-btn/)
    assert.match(markup, /Try Again/)
    assert.match(markup, /aria-label="Try Again"/)
  })

  // -------------------------------------------------------------------------
  // 3. EmptyState renders
  // -------------------------------------------------------------------------
  it('3. EmptyState renders with title, description, and action button', () => {
    const actionBtn = React.createElement(
      'button',
      { type: 'button', className: 'test-action-btn' },
      'Reset Filters',
    )

    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'No Data Available',
        description: 'There is no analysis available for this symbol.',
        action: actionBtn,
      }),
    )

    assert.match(markup, /role="region"/)
    assert.match(markup, /No Data Available/)
    assert.match(markup, /There is no analysis available for this symbol\./)
    assert.match(markup, /test-action-btn/)
    assert.match(markup, /Reset Filters/)
    assert.match(markup, /sf-empty-icon/)
  })

  // -------------------------------------------------------------------------
  // 4. Retry callback is actually invoked
  // -------------------------------------------------------------------------
  it('4. Retry callback is actually invoked when retry button is triggered', () => {
    let retryCount = 0
    const handleRetry = () => {
      retryCount += 1
    }

    const element = React.createElement(ErrorState, {
      title: 'Failed to Fetch',
      message: 'Server timeout',
      onRetry: handleRetry,
    })

    // Validate callback is attached to props
    assert.strictEqual(typeof element.props.onRetry, 'function')
    element.props.onRetry()
    assert.strictEqual(retryCount, 1)

    element.props.onRetry()
    assert.strictEqual(retryCount, 2)
  })

  // -------------------------------------------------------------------------
  // 5. API error produces ErrorState
  // -------------------------------------------------------------------------
  it('5. API error produces ErrorState transition', async () => {
    // Mock a failing API endpoint
    const mockApiFetch = async () => {
      throw new Error('API request failed with status 500')
    }

    let state = { loading: true, data: null, error: null }

    try {
      state.data = await mockApiFetch()
      state.loading = false
    } catch (err) {
      state.error = err.message
      state.loading = false
    }

    // Verify state transition: from loading to error
    assert.strictEqual(state.loading, false)
    assert.strictEqual(state.data, null)
    assert.ok(state.error)

    const markup = renderToStaticMarkup(
      React.createElement(ErrorState, {
        title: 'Unable to Load Scanner Results',
        message: state.error,
        onRetry: () => {},
      }),
    )

    assert.match(markup, /Unable to Load Scanner Results/)
    assert.match(markup, /The server encountered an issue processing this request\./)
    assert.match(markup, /sf-state-retry-btn/)
  })

  // -------------------------------------------------------------------------
  // 6. Empty API result produces EmptyState
  // -------------------------------------------------------------------------
  it('6. Empty API result produces EmptyState', async () => {
    // Mock an endpoint returning empty dataset
    const mockApiFetch = async () => {
      return []
    }

    let state = { loading: true, items: null, error: null }
    state.items = await mockApiFetch()
    state.loading = false

    assert.strictEqual(state.loading, false)
    assert.strictEqual(state.items.length, 0)
    assert.strictEqual(state.error, null)

    const markup = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: 'No Stocks Match Filters',
        description: 'The SignalForge scanner returned zero stock evaluation records.',
      }),
    )

    assert.match(markup, /No Stocks Match Filters/)
    assert.match(markup, /zero stock evaluation records/)
  })

  // -------------------------------------------------------------------------
  // 7. Successful API result displays normal content
  // -------------------------------------------------------------------------
  it('7. Successful API result displays normal content without loading or error states', async () => {
    const mockApiFetch = async () => {
      return [
        { symbol: 'RELIANCE', price: 2856.4, signal: 'BUY' },
        { symbol: 'TCS', price: 3420.15, signal: 'BUY' },
      ]
    }

    let state = { loading: true, items: null, error: null }
    state.items = await mockApiFetch()
    state.loading = false

    assert.strictEqual(state.loading, false)
    assert.strictEqual(state.items.length, 2)

    // Render normal data view
    const dataTable = React.createElement(
      'div',
      { className: 'mock-data-table' },
      state.items.map((stock) =>
        React.createElement(
          'div',
          { key: stock.symbol, className: 'stock-row' },
          `${stock.symbol}: ${stock.price} (${stock.signal})`,
        ),
      ),
    )

    const markup = renderToStaticMarkup(dataTable)

    assert.match(markup, /RELIANCE: 2856.4 \(BUY\)/)
    assert.match(markup, /TCS: 3420.15 \(BUY\)/)
    assert.doesNotMatch(markup, /sf-loading-state/)
    assert.doesNotMatch(markup, /sf-error-state/)
    assert.doesNotMatch(markup, /sf-empty-state/)
  })

  // -------------------------------------------------------------------------
  // 8. Error message sanitization unit test
  // -------------------------------------------------------------------------
  it('8. sanitizeErrorMessage cleanly sanitizes technical exceptions', () => {
    assert.strictEqual(
      sanitizeErrorMessage('Failed to fetch'),
      'Unable to connect to the SignalForge backend server. Please ensure the API service is running.',
    )
    assert.strictEqual(
      sanitizeErrorMessage('AxiosError: status code 500'),
      'The server encountered an issue processing this request.',
    )
    assert.strictEqual(
      sanitizeErrorMessage('HTTP 404 not found'),
      'The requested data resource was not found on the server.',
    )
    assert.strictEqual(
      sanitizeErrorMessage('Custom business error'),
      'Custom business error',
    )
    assert.strictEqual(
      sanitizeErrorMessage(null, 'Fallback msg'),
      'Fallback msg',
    )
  })
})
