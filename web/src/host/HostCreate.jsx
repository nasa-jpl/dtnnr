import { Text } from '@mantine/core';
import { useCreateHostMutation } from '../utils/queries';
import HostForm from './HostForm';

function HostCreate() {
  return (
    <HostForm
      mutation={useCreateHostMutation()}
      formTitle="Create Host"
      formDescription={
        <Text c="dimmed" size="sm">
          Please fill out this form to create a new host. After the host has
          been created, you will be redirected to the host's page where you can
          add more details such as destinations and links.
        </Text>
      }
      method="POST"
    />
  );
}

export default HostCreate;
