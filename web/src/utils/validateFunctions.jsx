/**
 * Returns a function to be used for Mantine Form validation.
 * Checks if value is within [0, 2^63 - 1], allows null value.
 * @param {string} message error message to display
 * @returns validation function
 */
export function isInBigIntRange(
  message = 'Value must be between 0 and 2^63 - 1',
) {
  return (value) =>
    value !== '' &&
    value !== undefined &&
    (BigInt(value) < 0 || BigInt(value) > 9223372036854775807n)
      ? message
      : null;
}

/**
 * Returns a function to be used for Mantine Form validation.
 * Checks if value is within [1, 2^63 - 1], allows null value.
 * @param {string} message error message to display
 * @returns validation function
 */
export function isInBigIntRangePositive(
  message = 'Value must be between 1 and 2^63 - 1',
) {
  return (value) =>
    value !== '' &&
    value !== undefined &&
    (BigInt(value) < 1 || BigInt(value) > 9223372036854775807n)
      ? message
      : null;
}

/**
 * Returns a function to be used for Mantine Form validation.
 * Checks if value is within [0, 2^31 - 1], allows null value.
 * @param {string} message error message to display
 * @returns validation function
 */
export function isInIntRange(message = 'Value must be between 0 and 2^31 - 1') {
  return (value) =>
    value !== '' &&
    value !== undefined &&
    (Number(value) < 0 || Number(value) > 2147483647)
      ? message
      : null;
}

/**
 * Returns a function to be used for Mantine Form validation.
 * Checks if value is within [0, 2^15 - 1], allows null value.
 * @param {string} message error message to display
 * @returns validation function
 */
export function isInSmallIntRange(
  message = 'Value must be between 0 and 2^15 - 1',
) {
  return (value) =>
    value !== '' &&
    value !== undefined &&
    (Number(value) < 0 || Number(value) > 32767)
      ? message
      : null;
}
