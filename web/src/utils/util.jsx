import { useMediaQuery } from '@mantine/hooks';

export const useIsMobile = () => useMediaQuery('(max-width: 48em)');

export function drill(obj, key) {
  let arr = key.split('.');
  let res = obj[arr[0]];
  if (
    [
      'allocator_id',
      'non_volatile_storage_size',
      'sdr_wm_size',
      'wm_size',
      'service_number',
    ].includes(arr[0])
  ) {
    // Convert String to Number
    // BigInt is more expensive than Number, so only covnert if necessary
    let number = +res;
    res = Number.isSafeInteger(number) ? number : BigInt(res);
  }
  for (let str of arr.slice(1)) {
    if (res === null) {
      return '';
    } else if (
      [
        'allocator_id', // from allocator.allocator_id
      ].includes(str)
    ) {
      // Convert String to Number
      let number = +res[str];
      res = Number.isSafeInteger(number) ? number : BigInt(res[str]);
    } else {
      res = res[str];
    }
  }
  return res;
}

export function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

// https://github.com/you-dont-need/You-Dont-Need-Lodash-Underscore#_sortby-and-_orderby
export const sortBy = (key) => {
  return (a, b) =>
    drill(a, key) > drill(b, key) ? 1 : drill(b, key) > drill(a, key) ? -1 : 0;
};

/**
 * Convert ISO 3166-1 alpha-2 two-letter country codes to a pair of regional
 * indicator symbols. If the pair is a valid Unicode region code, then it is
 * an emoji flag sequence.
 *
 * Modified from https://github.com/thekelvinliu/country-code-emoji/blob/main/src/index.js
 * @param {string} cc ISO 3166-1 alpha-2 two-letter country code
 * @returns {string} pair of regional indicator symbols
 */
export function countryCodeToEmoji(cc) {
  if (!/^[A-Za-z]{2}$/.test(cc)) {
    throw new TypeError(
      `cc argument must be an ISO 3166-1 alpha-2 country code, but got
      '${typeof cc === 'string' ? cc : typeof cc}' instead.`,
    );
  }
  // Offset between uppercase ASCII and regional indicator symbols
  let offset = 127397;
  let codePoints = [...cc.toUpperCase()].map((c) => c.codePointAt() + offset);
  return String.fromCodePoint(...codePoints);
}

/**
 * Flattens a nested Object to an object that's one level deep.
 *
 * Modified from https://stackoverflow.com/a/59787588
 * @param {Object} obj object to flatten
 * @param {string} [prefix] prefix to add before each key, also used for recursion
 * @param {Object} [result={}] result to add nested fields to
 * @returns {Object} result with nested fields added to it
 **/
export function flatten(obj, prefix = '', result = {}) {
  // Preserve empty objects and arrays, they are lost otherwise
  if (
    prefix &&
    typeof obj === 'object' &&
    obj !== null &&
    Object.keys(obj).length === 0
  ) {
    result[prefix] = Array.isArray(obj) ? [] : {};
    return result;
  }

  prefix = prefix ? `${prefix}.` : '';

  for (const i in obj) {
    if (Object.hasOwn(obj, i)) {
      // Only recurse on true objects and arrays, ignore custom classes like dates
      if (
        typeof obj[i] === 'object' &&
        // Do not recurse if the Array is not an Array of objects
        ((Array.isArray(obj[i]) && typeof obj[i].at(0) === 'object') ||
          Object.prototype.toString.call(obj[i]) === '[object Object]') &&
        obj[i] !== null
      ) {
        // Recursion on deeper objects
        flatten(obj[i], prefix + i, result);
      } else {
        if (Array.isArray(obj[i]) && typeof obj[i].at(0) === 'string') {
          result[prefix + i] = obj[i].join(' ');
        } else {
          result[prefix + i] = obj[i];
        }
      }
    }
  }
  return result;
}

/**
 * Returns true if object is empty.
 * Taken from https://stackoverflow.com/a/32108184
 * @param {Object} obj
 * @returns
 */
export function isEmpty(obj) {
  for (const prop in obj) {
    if (Object.hasOwn(obj, prop)) {
      return false;
    }
  }
  return true;
}

/**
 * Scrolls to `element` and optionally focuses on it.
 * A NumberInput component will not be focused if the value is '' or
 * is not a safe integer, regardless of `focus`.
 *
 * @param {Element} element Element to scroll and optionally focus on
 * @param {boolean} focus true if `element` should be focused
 */
export function scrollElementIntoView(element, focus = true) {
  element?.scrollIntoView({ /* behavior: 'smooth', */ block: 'center' });
  // Do not focus on the error element when the element is a NumberInput
  // with an empty value or with an unsafe integer value.
  // NumberInput works in such a way that it triggers a change event on
  // the element when the value is either of these. The forms are set
  // up to clear field errors on change, so the error message will be
  // removed on a blur event.
  // This still isn't great; if the user manually focuses on the element
  // and then unfocuses, the error message will still be cleared. But there's
  // at least one extra step which should suffice for most cases.
  // Ideally, we only want the error message to disappear when the user actually
  // types something. NumberInput is implemented this way to prevent
  // errors when dealing with unsafe integers, so I'm not sure if there's
  // an alterantive implementation that can deal with unsafe integers while
  // also not firing a change event.
  const shouldNotFocusNumberInput =
    element?.classList?.contains('mantine-NumberInput-input') &&
    (element?.value === '' || !Number.isSafeInteger(element?.value));
  if (focus && !shouldNotFocusNumberInput) {
    element?.focus({ preventScroll: true });
  }
}

/**
 * Call `callback` when `target` is visible inside `root`.
 * @param {Element} target targetElement for IntersectionObserver.observe()
 * @param {Function} callback function to call after target is visible
 * @param {Element} root value to use for IntersectionObserver.root
 */
export function waitForVisibleElement(target, callback, root) {
  new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.intersectionRatio > 0) {
          observer.disconnect();
          callback();
        }
      });
    },
    { root: root || document },
  ).observe(target);
}

/**
 * Call `callback` when the element with id `addedId` is in the document
 * after observing changes (specified by `observeOptions`) under `observeTarget`.
 *
 * Modified from https://stackoverflow.com/a/38882022
 * @param {Number} addedId id of element to look for
 * @param {Function} callback function to call if element is in the document
 * @param {Element} observeTarget target for MutationObserver.observe()
 * @param {Object} observeOptions options for MutationObserver.observe()
 */
export function waitForAddedElement(
  addedId,
  callback,
  observeTarget = document,
  observeOptions = { subtree: true, childList: true }, //, attributes: true }
) {
  new MutationObserver((_mutations, observer) => {
    const el = document.getElementById(addedId);
    if (el) {
      observer.disconnect();
      callback(el);
    }
  }).observe(observeTarget, observeOptions);
}

/**
 * Waits for FormErrorSection component to render, and then scrolls to it.
 */
export function scrollToErrorSection() {
  // The Alert in the FormErrorSection component has the id form-error-alert
  // If we modify FormErrorSection, we may have to modify this too.
  waitForAddedElement('form-error-alert', (el) => scrollElementIntoView(el));
}

// TODO: this should eventually be deleted once everything is migrated to
// setAndScrollForExtras();
/**
 * Sets form errors with messages from `error` and scrolls to the first
 * element with an error.
 *
 * @param {Object} form returned from @mantine/form use-form hook
 * @param {Object} error object with detail.json
 */
export function setAndScrollToJSONError(form, error) {
  form.setErrors(flatten(error.detail.json));
  let elements = Object.keys(flatten(error.detail.json))
    .map((dataPath) => form.getInputNode(dataPath))
    .filter((el) => !!el);
  elements.sort(
    (a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top,
  );
  scrollElementIntoView(elements[0]);
}

/**
 * Sets form errors with messages from `extra` and scrolls to the first
 * element with an error.
 *
 * `extra` is an array of ProblemDetailsExtraSchema which are objects like
 * ```
 * {
 *   message: string,
 *   key: string,
 *   source: string
 * }
 * ```
 * This assumes that the form key is identical with the key used in request
 * bodies.
 *
 * @param {Object} form returned from @mantine/form use-form hook
 * @param {Array} extra array of problem details extra schema objects
 */
export function setAndScrollForExtra(form, extra) {
  let errors = {};
  for (let { key, message } of extra) {
    key = key.replaceAll('[', '.').replaceAll(']', '');
    if (errors[key] === undefined) {
      errors[key] = message;
    } else {
      errors[key] += `; ${message}`;
    }
  }
  form.setErrors(errors);
  let elements = Object.keys(errors)
    .map((dataPath) => form.getInputNode(dataPath))
    .filter((el) => !!el);
  elements.sort(
    (a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top,
  );
  scrollElementIntoView(elements[0]);
}
