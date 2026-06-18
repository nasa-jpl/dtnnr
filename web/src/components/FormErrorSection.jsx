import { Alert, Space } from '@mantine/core';

export function FormErrorSection({ message, setErrorSection }) {
  return (
    <>
      <Space h="md" />
      <Alert
        variant="light"
        color="red"
        title="Error"
        withCloseButton
        onClose={() => setErrorSection('')}
        className="show-white-space"
        id="form-error-alert"
      >
        {message}
      </Alert>
    </>
  );
}
