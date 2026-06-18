import { Box, Button, Group, Stack } from '@mantine/core';

export function DangerConfirmModal({
  description,
  confirmMessage,
  cancelMessage,
  closeModals,
  onConfirm,
}) {
  const confirmButton = (
    // Since we call useMutation() outside of this component, and modal manager
    // doesn't support dynamic content, we can't show loading state here.
    // useMutation() would have to be called after the modal was opened for
    // us to control that state from here, but we'd have to rewrite a lot /
    // create a lot of components for a relatively minor feature (loading state
    // for this button).
    <Button
      color="red"
      onClick={() => {
        closeModals();
        onConfirm();
      }}
    >
      {confirmMessage}
    </Button>
  );
  const cancelButton = (
    <Button variant="default" onClick={closeModals}>
      {cancelMessage}
    </Button>
  );

  return (
    <Box maw={600} mx="auto">
      {description}
      <Stack hiddenFrom="xs" mt="md">
        {confirmButton}
        {cancelButton}
      </Stack>
      <Group visibleFrom="xs" mt="md" justify="flex-end">
        {cancelButton}
        {confirmButton}
      </Group>
    </Box>
  );
}
