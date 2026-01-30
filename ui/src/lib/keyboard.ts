/**
 * Keyboard event utilities
 *
 * Helpers for handling keyboard events, particularly for IME-aware input handling.
 */

/**
 * Check if an Enter keypress should trigger form submission.
 *
 * Returns false during IME composition (e.g., Japanese, Chinese, Korean input)
 * to prevent accidental submission while selecting characters.
 *
 * @param e - The keyboard event from React
 * @param allowShiftEnter - If true, Shift+Enter returns false (for multiline input)
 * @returns true if Enter should submit, false if it should be ignored
 *
 * @example
 * // In a chat input (Shift+Enter for newline)
 * if (isSubmitEnter(e)) {
 *   e.preventDefault()
 *   handleSend()
 * }
 *
 * @example
 * // In a single-line input (Enter always submits)
 * if (isSubmitEnter(e, false)) {
 *   handleSubmit()
 * }
 */
export function isSubmitEnter(
  e: React.KeyboardEvent,
  allowShiftEnter: boolean = true
): boolean {
  if (e.key !== 'Enter') return false
  if (allowShiftEnter && e.shiftKey) return false
  if (e.nativeEvent.isComposing) return false
  return true
}
