import {
  CheckIcon,
  Combobox,
  Input,
  InputBase,
  ScrollArea,
  useCombobox,
} from '@mantine/core';
import {
  getCountryCodeForRegionCode,
  getSupportedRegionCodes,
} from 'awesome-phonenumber';
import { memo } from 'react';
import { countryCodeToEmoji } from '../utils/util';
import classes from './CountryCodeSelect.module.css';

const regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
const sortedRegionCodes = getSupportedRegionCodes()
  .map((rc) => ({
    rc: rc,
    emoji: countryCodeToEmoji(rc),
    name: regionNames.of(rc),
    cc: getCountryCodeForRegionCode(rc),
  }))
  .sort((a, b) => a.name.localeCompare(b.name, { ignorePunctuation: true }));
const options = sortedRegionCodes.map((o) => (
  <Combobox.Option value={o.rc} key={o.rc} className={classes.optionContainer}>
    {o.emoji} {o.name} (+{o.cc})
  </Combobox.Option>
));

// These options are expensive to render, so try to minimize the rendering
// and work needed to create them.
// There's only one active option, so not every Option needs to change.
// And if the selected option (given by the index) hasn't changed, then
// there's no need to change.
const OptionsOneActive = memo(function OptionsOneActive({ index }) {
  let res = options.slice();
  let o = sortedRegionCodes.at(index);
  res[index] = (
    <Combobox.Option
      value={o.rc}
      key={o.rc}
      className={classes.optionContainer}
      active
    >
      <CheckIcon className={classes.icon} />
      {o.emoji} {o.name} (+{o.cc})
    </Combobox.Option>
  );
  return res;
});

export const CountryCodeSelect = memo(function CountryCodeSelect({
  // countryCode comes from the parent
  countryCode = 'US',
  setCountryCode,
  handleChange = () => {},
  ...otherProps
}) {
  const combobox = useCombobox({
    onDropdownClose: () => combobox.resetSelectedOption(),
    onDropdownOpen: (eventSource) => {
      if (eventSource === 'keyboard') {
        combobox.selectActiveOption();
      } else {
        combobox.updateSelectedOptionIndex('active', { scrollIntoView: true });
      }
    },
  });

  return (
    <Combobox
      store={combobox}
      position="bottom-start"
      width="max-content"
      onOptionSubmit={(val) => {
        if (val !== countryCode) {
          setCountryCode(val);
          handleChange(val, getCountryCodeForRegionCode(val));
        }
        combobox.updateSelectedOptionIndex('active');
        combobox.closeDropdown();
      }}
      {...otherProps}
    >
      <Combobox.Target>
        <InputBase
          component="button"
          type="button"
          pointer
          rightSection={<Combobox.Chevron />}
          rightSectionPointerEvents="none"
          onClick={() => {
            combobox.toggleDropdown();
          }}
        >
          {countryCodeToEmoji(countryCode) || (
            <Input.Placeholder>?</Input.Placeholder>
          )}
        </InputBase>
      </Combobox.Target>

      <Combobox.Dropdown>
        <Combobox.Options>
          <ScrollArea.Autosize mah={200} type="scroll">
            <OptionsOneActive
              index={sortedRegionCodes.findIndex((o) => o.rc === countryCode)}
            />
          </ScrollArea.Autosize>
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
});
