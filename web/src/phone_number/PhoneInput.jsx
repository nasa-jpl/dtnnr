import { TextInput } from '@mantine/core';
import { useUncontrolled } from '@mantine/hooks';
import {
  getAsYouType,
  getCountryCodeForRegionCode,
  parsePhoneNumber,
} from 'awesome-phonenumber';
import { useCallback, useEffect, useState } from 'react';
import { CountryCodeSelect } from './CountryCodeSelect';
import classes from './PhoneInput.module.css';

export function PhoneInput({
  value,
  defaultValue,
  onChange,
  onFocus,
  onBlur,
  error,
  ...otherProps
}) {
  const [_value, handleChange] = useUncontrolled({
    value,
    defaultValue,
    finalValue: 'Final',
    onChange,
  });
  // Manage the value with our own useState() instead of the one given by
  // useUncontrolled() so we can take advantage of passing an update function
  // to setValue2. This means the callback function passed to CountryCodeSelect
  // doesn't change each time the phone number changes, so less re-rendering
  // of CountryCodeSelect
  const [value2, setValue2] = useState(defaultValue ?? '');
  const [regionCode, setRegionCode] = useState(
    parsePhoneNumber(defaultValue)?.regionCode ?? 'US',
  );
  const [formatter, setFormatter] = useState(getAsYouType(regionCode));

  useEffect(() => {
    formatter.reset(defaultValue);
  }, [defaultValue, formatter]);

  // formatter is mutable, but React wants us to treat them as immutable.
  // General function to call when we use .addChar(), .removeChar(), or .reset().
  // N.b., the callback passed to CountryCodeSelect does not use this function
  function updateFormatter() {
    if (
      getCountryCodeForRegionCode(
        formatter.getPhoneNumber().regionCode ?? regionCode,
      ) !== getCountryCodeForRegionCode(regionCode)
    ) {
      // Comparing the number instead of the region code means we don't keep
      // switching back to US for most +1 numbers. There's a trade off of the
      // flag not updating when a number is clearly CA or some other +1
      // region. Library doesn't know that +1 250-555-5555 is a CA phone number
      // until the last digit, so if you added / delete one character, it would
      // switch back to the US flag. I don't see a good way to implement this.
      setRegionCode(formatter.getPhoneNumber().regionCode);
      if (formatter.getPhoneNumber()?.number !== undefined) {
        let newFormatter = getAsYouType(formatter.getPhoneNumber().regionCode);
        newFormatter.reset(formatter.getPhoneNumber().number.input);
        setFormatter(newFormatter);
      }
    } else {
      setFormatter(formatter);
    }
  }

  const f = useCallback(
    (region, num) => {
      // getPhoneNumber().number.input doesn't keep track of whitespace in front
      // of the string, so if we had something like "  +44 123" it would get replaced
      // with "+1 123". So we should set the value depending on value2, not input
      setValue2((value2) => {
        let value3 = value2;
        let s = '';
        let firstNonwhitespaceIndex = value3.search(/\S|$/);
        if (
          value3.startsWith(
            `+${getCountryCodeForRegionCode(regionCode)}`,
            firstNonwhitespaceIndex,
          )
        ) {
          s = `${value3.slice(0, firstNonwhitespaceIndex)}+${num}${value3.slice(firstNonwhitespaceIndex + getCountryCodeForRegionCode(regionCode).toString().length + 1)}`;
        } else if (value3.search(/\S/) === -1 && value3.length <= 1) {
          // When we have an empty string or string with one whitespace character,
          // the else clause would give us a trailing whitespace which messes up
          // the formatter, so don't add the whitespace in this case.
          s = `+${num}`;
        } else {
          s = `+${num} ${value3}`;
        }
        let newFormatter = getAsYouType(region);
        newFormatter.reset(s);
        setFormatter(newFormatter);
        handleChange(s);
        return s;
      });
    },
    [regionCode, handleChange],
  );

  return (
    <div className={classes.gridWrapper}>
      <CountryCodeSelect
        countryCode={regionCode}
        setCountryCode={setRegionCode}
        handleChange={f}
        className={classes.countryCodeSelect}
      />
      <TextInput
        type="tel"
        value={value2}
        onInput={(e) => {
          let inputEvent = e.nativeEvent;
          let target = e.target;
          // addChar() and removeChar() only work on the last character, so
          // we'll only use them when the cursor is at the end and when the
          // insertion or deletion only changes the length by 1.
          if (
            target.selectionStart === target.value?.length &&
            [value2.length + 1, value2.length - 1].includes(target.value.length)
          ) {
            // Only addChar() if the input is exactly one digit
            if (/^\d{1}$/.test(inputEvent.data)) {
              // If formatter.getPhoneNumber().number.input is "+44", then
              // .addChar("1") will make input "+44 1".
              // Similarly, if input is "+44 1234" then .addChar("5") will
              // make input "+44 1234 5".
              // So it looks like .addChar() sets input to the formatted result,
              // whereas we ideally would want input to be the raw input.
              // E.g., in Google Contacts, if we input "+44250555" the
              // number is displayed as "+44 25 0555", if we then switch to CA,
              // the number is displayed as "+1 250-555". If we switch back to
              // GB, we get "+44 25 0555" again.
              // In contrast, our "+44 25 0555" merely replaces the country
              // code to make "+1 25 0555".
              // TODO: if interested, we could attain something similar by
              // keeping track of the raw input. In updateFormatter(), when
              let x = formatter.addChar(inputEvent.data);
              setValue2(x);
              handleChange(x);
              updateFormatter();
              return;
            } else if (
              value2.trimEnd().length === value2.length &&
              inputEvent.inputType.startsWith('deleteContent')
            ) {
              // Only removeChar() when one character is deleted
              let x = formatter.removeChar();
              setValue2(x);
              handleChange(x);
              updateFormatter();
              return;
            }
          }
          // Fallback: if nothing matched earlier then reset()
          formatter.reset(target.value);
          if (inputEvent.inputType.startsWith('deleteContent')) {
            setValue2(target.value);
            handleChange(target.value);
          } else {
            setValue2(formatter.number());
            handleChange(formatter.number());
          }
          updateFormatter();
        }}
        onFocus={onFocus}
        onBlur={onBlur}
        error={error}
        className={classes.phoneInput}
        {...otherProps}
      />
    </div>
  );
}
