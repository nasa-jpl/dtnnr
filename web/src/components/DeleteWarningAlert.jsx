import { Alert, Text } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';

export function DeleteWarningAlert({ text, contactParentName, ...otherProps }) {
  return (
    <Alert
      variant="light"
      color="red"
      title="Warning"
      icon={<IconAlertCircle className="icon-16-px" />}
      {...otherProps}
    >
      {text}
      {contactParentName && (
        <Text size="sm">
          Any point of contact that is only associated with this{' '}
          {contactParentName} (and no other allocator, operator, host, or node)
          will be deleted.
        </Text>
      )}
    </Alert>
  );
}
