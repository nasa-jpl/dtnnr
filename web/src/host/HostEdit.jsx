import { Text } from '@mantine/core';
import { useUpdateHostMutation } from '../utils/queries';
import HostForm from './HostForm';

function HostEdit({ initialHost, closeModals }) {
  return (
    <HostForm
      initialHost={initialHost}
      closeModals={closeModals}
      mutation={useUpdateHostMutation(initialHost.host_id)}
      formDescription={
        <>
          <Text c="dimmed" size="sm">
            Fill out this form to update the host identified by host ID{' '}
            {initialHost.host_id}.
          </Text>
          <Text c="dimmed" size="sm">
            <b>Note:</b> if the host has nodes that are under an operator,
            setting operator_id to null will also set all nodes under the host
            to have a null operator_id.
          </Text>
        </>
      }
      method="PATCH"
    />
  );
}

export default HostEdit;
