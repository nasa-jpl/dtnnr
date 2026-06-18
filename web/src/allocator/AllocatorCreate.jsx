import { Text } from '@mantine/core';
import { useCreateAllocatorMutation } from '../utils/queries';
import AllocatorForm from './AllocatorForm';

function AllocatorCreate() {
  return (
    <AllocatorForm
      mutation={useCreateAllocatorMutation()}
      formTitle="Create allocator"
      formDescription={
        <Text c="dimmed" size="sm">
          Please fill out this form to create an allocator. After the allocator
          has been created, you will be redirected to the allocator's page where
          you can add point of contact information.
        </Text>
      }
      method="POST"
    />
  );
}

export default AllocatorCreate;
