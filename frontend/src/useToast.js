/**
 * useToast.js
 * Creates the ToastContext and exports the useToast hook.
 *
 * Separated from ToastContext.jsx so the component file only exports
 * React components (satisfies react/only-export-components lint rule).
 *
 * Usage:
 *   import { useToast } from './useToast'
 *
 *   const toast = useToast()
 *   toast.success('RELIANCE added to Watchlist.')
 *   toast.error('Unable to load scanner.', { title: 'Load Error' })
 *   toast.warning('Select a stock first.')
 *   toast.info('Analysis started for RELIANCE.')
 */

import { createContext, useContext } from 'react'

// The context object — created here and imported by ToastContext.jsx (the provider)
export const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used inside <ToastProvider>')
  }
  return ctx
}
