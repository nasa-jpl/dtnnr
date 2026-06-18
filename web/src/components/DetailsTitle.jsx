import { Button, Group, Stack, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconCopy, IconEdit, IconTrash } from '@tabler/icons-react';
import { useNavigate } from '@tanstack/react-router';
import { useContext } from 'react';
import AuthContext from '../AuthContext';
import { Route as nodesRoute } from '../routes/_home.nodes';
import { useModalStore } from '../stores/useModalStore';
import { formatGeneralError } from '../utils/formatFunctions';
import { DangerConfirmModal } from './DangerConfirmModal';

function DetailsTitle({
  name,
  editModalTitle,
  handleEditRecordModal,
  copyModalTitle,
  handleCopyRecordModal,
  deleteModalTitle,
  deleteModalDescription,
  confirmDeleteMessage,
  record,
  deleteRecordMutation,
}) {
  const { currentUser } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = window.location.href;
  const openModal = useModalStore((s) => s.open);
  const closeModal = useModalStore((s) => s.close);

  // TODO: show these buttons with loading state when the buttons
  // inside the modals are also in loading state.
  let buttons = (
    <>
      {/* TODO: we need to abstract the logic from here so the different pages can
      specify whether to show the buttons or not */}
      {currentUser && copyModalTitle && (
        <Button
          style={{ marginLeft: 'auto' }}
          variant="light"
          leftSection={<IconCopy className="icon-14-px" />}
          onClick={() =>
            openModal(handleCopyRecordModal(closeModal), {
              title: copyModalTitle,
              size: 'lg',
            })
          }
        >
          Copy
        </Button>
      )}
      {currentUser && (
        <Button
          style={!copyModalTitle && { marginLeft: 'auto' }}
          leftSection={<IconEdit className="icon-14-px" />}
          onClick={() =>
            openModal(handleEditRecordModal(closeModal), {
              title: editModalTitle,
              size: ' lg',
            })
          }
        >
          Edit
        </Button>
      )}
      {currentUser && (
        <Button
          color="red"
          leftSection={<IconTrash className="icon-14-px" />}
          loading={deleteRecordMutation.isPending}
          onClick={() =>
            openModal(
              <DangerConfirmModal
                description={deleteModalDescription}
                confirmMessage={confirmDeleteMessage}
                cancelMessage="No don't delete"
                closeModals={closeModal}
                onConfirm={() =>
                  deleteRecordMutation.mutate(record, {
                    onSuccess: () =>
                      notifications.show({
                        title: 'Successfully deleted record',
                        message:
                          'You will be taken to the home page when' +
                          ' this message closes.',
                        onClose: () => {
                          if (location === window.location.href) {
                            navigate({ to: nodesRoute.to });
                          }
                        },
                      }),
                    onError: (error) =>
                      notifications.show({
                        title: 'Failed to delete record',
                        message: formatGeneralError(error),
                        withCloseButton: true,
                        color: 'red',
                      }),
                  })
                }
              />,
              { title: deleteModalTitle },
            )
          }
        >
          Delete
        </Button>
      )}
    </>
  );

  return (
    <>
      <Stack hiddenFrom="xs">
        <Title>{name}</Title>
        <Group gap="xs" grow>
          {buttons}
        </Group>
      </Stack>
      <Group visibleFrom="xs">
        <Title>{name}</Title>
        {buttons}
      </Group>
    </>
  );
}

export default DetailsTitle;
