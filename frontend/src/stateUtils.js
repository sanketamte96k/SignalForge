/**
 * Utility functions for frontend state handling and error sanitization.
 */

export function sanitizeErrorMessage(error, fallback = 'Unable to complete request.') {
  if (!error) return fallback
  const raw = typeof error === 'string' ? error : error?.message || fallback

  if (/Failed to fetch|NetworkError|ERR_CONNECTION_REFUSED|API unavailable/i.test(raw)) {
    return 'Unable to connect to the SignalForge backend server. Please ensure the API service is running.'
  }
  if (/status (?:code )?500/i.test(raw)) {
    return 'The server encountered an issue processing this request.'
  }
  if (/(?:status (?:code )?|HTTP )?404/i.test(raw)) {
    return 'The requested data resource was not found on the server.'
  }
  if (/timeout/i.test(raw)) {
    return 'The request timed out while waiting for a response from the server.'
  }
  return raw
}
