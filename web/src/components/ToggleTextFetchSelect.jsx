import { ActionIcon, TextInput } from '@mantine/core';
import { IconEdit, IconEditOff } from '@tabler/icons-react';
import FetchSelect from './FetchSelect';

export function ToggleTextFetchSelect({
  editing,
  canEdit = true,
  initialValue,
  handleFormat,
  setFieldValue,
  ...otherProps
}) {
  const rightSection = (
    <ActionIcon
      variant="subtle"
      color="gray"
      onClick={() => {
        setFieldValue(!editing ? null : undefined);
      }}
    >
      {editing ? (
        <IconEditOff className="icon-20-px" />
      ) : (
        <IconEdit className="icon-20-px" />
      )}
    </ActionIcon>
  );

  let textValue = handleFormat(initialValue)?.label ?? 'Null';

  if (!editing) {
    delete otherProps.queryKey;
    delete otherProps.url;
  }

  return editing ? (
    <FetchSelect
      // TODO: maybe make this left section? it clashes with the Refresh button
      rightSectionPointerEvents={canEdit ? 'auto' : false}
      rightSection={canEdit ? rightSection : false}
      initialValue={initialValue}
      handleFormat={handleFormat}
      {...otherProps}
    />
  ) : (
    <TextInput
      variant="unstyled"
      readOnly
      rightSectionPointerEvents={canEdit ? 'auto' : false}
      rightSection={canEdit ? rightSection : false}
      {...otherProps}
      defaultValue={textValue.slice(textValue.indexOf(' ') + 1)}
    />
  );
}
