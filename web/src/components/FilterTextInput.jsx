import { TextInput } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';

function FilterTextInput({
  label,
  description,
  placeholder,
  handleSetQuery,
  queryIndex,
  defaultValue,
  ...otherProps
}) {
  return (
    <TextInput
      label={label}
      description={description}
      placeholder={placeholder}
      leftSection={<IconSearch className="icon-16-px" />}
      defaultValue={defaultValue}
      onChange={(e) => handleSetQuery(queryIndex, e.currentTarget.value)}
      {...otherProps}
    />
  );
}

export default FilterTextInput;
