import React from 'react'
import { sanitizeErrorMessage } from './stateUtils.js'
import './StateViews.css'

/**
 * Reusable animated SVG spinner matching SignalForge blue/cyan accent.
 */
export function LoadingSpinner({ size = 'medium', className = '' }) {
  return (
    <div
      className={`sf-spinner sf-spinner-${size} ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 38 38" className="sf-spinner-svg">
        <circle
          className="sf-spinner-track"
          cx="19"
          cy="19"
          r="15"
          fill="none"
          strokeWidth="3"
        />
        <circle
          className="sf-spinner-head"
          cx="19"
          cy="19"
          r="15"
          fill="none"
          strokeWidth="3"
          strokeDasharray="70"
          strokeDashoffset="20"
        />
      </svg>
    </div>
  )
}

/**
 * Global LoadingState component.
 */
export function LoadingState({
  title = 'Loading...',
  description = 'Fetching data from SignalForge backend...',
  compact = false,
  className = '',
  ariaLabel,
}) {
  return (
    <div
      className={`sf-state-container sf-loading-state ${compact ? 'sf-state-compact' : ''} ${className}`}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={ariaLabel || title}
    >
      <LoadingSpinner size={compact ? 'small' : 'medium'} />
      <div className="sf-state-text-block">
        {title && <strong className="sf-state-title">{title}</strong>}
        {description && <p className="sf-state-description">{description}</p>}
      </div>
    </div>
  )
}

/**
 * Global ErrorState component with user-friendly messaging and optional retry button.
 */
export function ErrorState({
  title = 'Unable to Load Data',
  message,
  error,
  onRetry,
  retryLabel = 'Try Again',
  compact = false,
  className = '',
}) {
  const displayMessage = sanitizeErrorMessage(message || error)

  return (
    <div
      className={`sf-state-container sf-error-state ${compact ? 'sf-state-compact' : ''} ${className}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="sf-state-icon sf-error-icon" aria-hidden="true">
        <svg
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

      <div className="sf-state-text-block">
        <strong className="sf-state-title">{title}</strong>
        {displayMessage && <p className="sf-state-description">{displayMessage}</p>}
      </div>

      {typeof onRetry === 'function' && (
        <button
          type="button"
          className="sf-state-retry-btn"
          onClick={onRetry}
          aria-label={retryLabel}
        >
          <svg
            className="sf-retry-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" />
            <path d="M21 3v5h-5" />
          </svg>
          <span>{retryLabel}</span>
        </button>
      )}
    </div>
  )
}

/**
 * Global EmptyState component for zero-data and filtered-out states.
 */
export function EmptyState({
  title = 'No Data Available',
  description = 'There is no data to display for this selection.',
  action,
  icon,
  compact = false,
  className = '',
}) {
  return (
    <div
      className={`sf-state-container sf-empty-state ${compact ? 'sf-state-compact' : ''} ${className}`}
      role="region"
      aria-label={title}
    >
      <div className="sf-state-icon sf-empty-icon" aria-hidden="true">
        {icon || (
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <line x1="8" y1="10" x2="16" y2="10" />
            <line x1="8" y1="14" x2="12" y2="14" />
          </svg>
        )}
      </div>

      <div className="sf-state-text-block">
        <strong className="sf-state-title">{title}</strong>
        {description && <p className="sf-state-description">{description}</p>}
      </div>

      {action && <div className="sf-state-action">{action}</div>}
    </div>
  )
}
