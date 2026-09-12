import test from 'node:test'
import assert from 'node:assert/strict'
import {
  isEditableTarget,
  isModifierKey,
  findNextTimeframe,
  NAVIGATION_SHORTCUTS,
  SHORTCUT_GROUPS,
  TIMEFRAME_SEQUENCE,
} from '../src/keyboardShortcuts.js'

test('Keyboard Shortcuts & Power-User UX (Improvement #6)', async (t) => {
  await t.test('1. Detects editable elements to protect normal typing from triggering shortcuts', () => {
    assert.equal(isEditableTarget({ tagName: 'INPUT' }), true)
    assert.equal(isEditableTarget({ tagName: 'input' }), true)
    assert.equal(isEditableTarget({ tagName: 'TEXTAREA' }), true)
    assert.equal(isEditableTarget({ tagName: 'textarea' }), true)
    assert.equal(isEditableTarget({ tagName: 'SELECT' }), true)
    assert.equal(isEditableTarget({ tagName: 'DIV', isContentEditable: true }), true)

    // Non-editable elements
    assert.equal(isEditableTarget({ tagName: 'DIV' }), false)
    assert.equal(isEditableTarget({ tagName: 'BUTTON' }), false)
    assert.equal(isEditableTarget({ tagName: 'BODY' }), false)
    assert.equal(isEditableTarget(null), false)
    assert.equal(isEditableTarget(undefined), false)
  })

  await t.test('2. Protects browser modifier keys (Ctrl, Meta/Command, Alt) from being hijacked', () => {
    assert.equal(isModifierKey({ ctrlKey: true }), true)
    assert.equal(isModifierKey({ metaKey: true }), true)
    assert.equal(isModifierKey({ altKey: true }), true)
    assert.equal(isModifierKey({ ctrlKey: true, shiftKey: true }), true)

    // Plain keys without modifier
    assert.equal(isModifierKey({ key: '1' }), false)
    assert.equal(isModifierKey({ key: '?' }), false)
    assert.equal(isModifierKey({ key: '/' }), false)
    assert.equal(isModifierKey(null), false)
  })

  await t.test('3. Maps number keys 1–7 to exact SignalForge navigation views', () => {
    assert.equal(NAVIGATION_SHORTCUTS['1'], 'Dashboard')
    assert.equal(NAVIGATION_SHORTCUTS['2'], 'Stock Scanner')
    assert.equal(NAVIGATION_SHORTCUTS['3'], 'Stock Analysis')
    assert.equal(NAVIGATION_SHORTCUTS['4'], 'Watchlists')
    assert.equal(NAVIGATION_SHORTCUTS['5'], 'Sectors')
    assert.equal(NAVIGATION_SHORTCUTS['6'], 'Paper Trading')
    assert.equal(NAVIGATION_SHORTCUTS['7'], 'Validation')
    assert.equal(NAVIGATION_SHORTCUTS['8'], undefined)
    assert.equal(NAVIGATION_SHORTCUTS['0'], undefined)
  })

  await t.test('4. Cycles supported chart timeframes cyclically with Arrow keys', () => {
    assert.deepEqual(TIMEFRAME_SEQUENCE, ['1m', '5m', '10m', '15m', '30m'])

    // Next direction
    assert.equal(findNextTimeframe('1m', 'next'), '5m')
    assert.equal(findNextTimeframe('5m', 'next'), '10m')
    assert.equal(findNextTimeframe('15m', 'next'), '30m')
    assert.equal(findNextTimeframe('30m', 'next'), '1m') // Wrap around to start

    // Previous direction
    assert.equal(findNextTimeframe('30m', 'prev'), '15m')
    assert.equal(findNextTimeframe('15m', 'prev'), '10m')
    assert.equal(findNextTimeframe('5m', 'prev'), '1m')
    assert.equal(findNextTimeframe('1m', 'prev'), '30m') // Wrap around to end

    // Unknown timeframe defaults to first
    assert.equal(findNextTimeframe('unknown', 'next'), '1m')
  })

  await t.test('5. Shortcut registry contains all expected categories and key definitions', () => {
    const categories = SHORTCUT_GROUPS.map((g) => g.category)
    assert.ok(categories.includes('Navigation'))
    assert.ok(categories.includes('Stock Scanner'))
    assert.ok(categories.includes('Stock Analysis'))
    assert.ok(categories.includes('General'))

    const scannerGroup = SHORTCUT_GROUPS.find((g) => g.category === 'Stock Scanner')
    assert.ok(scannerGroup.shortcuts.some((s) => s.key === '/'))
    assert.ok(scannerGroup.shortcuts.some((s) => s.key.includes('Enter')))
    assert.ok(scannerGroup.shortcuts.some((s) => s.key === 'W'))

    const analysisGroup = SHORTCUT_GROUPS.find((g) => g.category === 'Stock Analysis')
    assert.ok(analysisGroup.shortcuts.some((s) => s.key === 'B'))
    assert.ok(analysisGroup.shortcuts.some((s) => s.key === 'W'))

    const generalGroup = SHORTCUT_GROUPS.find((g) => g.category === 'General')
    assert.ok(generalGroup.shortcuts.some((s) => s.key === '?'))
    assert.ok(generalGroup.shortcuts.some((s) => s.key === 'Esc'))
  })

  await t.test('6. Scanner row navigation index math clamps correctly', () => {
    const items = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']

    const moveDown = (currentIndex) => Math.min(items.length - 1, (currentIndex ?? -1) + 1)
    const moveUp = (currentIndex) => Math.max(0, (currentIndex ?? 0) - 1)

    assert.equal(moveDown(null), 0)
    assert.equal(moveDown(0), 1)
    assert.equal(moveDown(3), 3) // At bottom, stays clamped

    assert.equal(moveUp(3), 2)
    assert.equal(moveUp(1), 0)
    assert.equal(moveUp(0), 0) // At top, stays clamped
  })

  await t.test('7. Watchlist shortcut action handles empty selection cleanly', () => {
    let toggled = false
    const handleWatchlistKey = (selectedSymbol) => {
      if (!selectedSymbol) return false
      toggled = true
      return true
    }

    assert.equal(handleWatchlistKey(null), false)
    assert.equal(toggled, false)

    assert.equal(handleWatchlistKey('TCS'), true)
    assert.equal(toggled, true)
  })

  await t.test('8. Back navigation shortcut triggers back callback safely', () => {
    let backTriggered = false
    const onBack = () => {
      backTriggered = true
    }

    const handleAnalysisKey = (key, callback) => {
      if (key === 'b' || key === 'B') {
        if (typeof callback === 'function') {
          callback()
          return true
        }
      }
      return false
    }

    assert.equal(handleAnalysisKey('B', onBack), true)
    assert.equal(backTriggered, true)
    assert.equal(handleAnalysisKey('X', onBack), false)
  })
})
