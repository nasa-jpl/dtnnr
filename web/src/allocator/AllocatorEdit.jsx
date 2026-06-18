import { Text } from '@mantine/core';
import { useUpdateAllocatorMutation } from '../utils/queries';
import AllocatorForm from './AllocatorForm';

function AllocatorEdit({ initialAllocator, closeModals }) {
  return (
    <AllocatorForm
      initialAllocator={initialAllocator}
      closeModals={closeModals}
      mutation={useUpdateAllocatorMutation(initialAllocator.allocator_id)}
      formDescription={
        <Text c="dimmed" size="sm">
          Fill out this form to update the allocator identified by allocator ID{' '}
          {initialAllocator.allocator_id}
        </Text>
      }
      method="PATCH"
    />
  );
}

export default AllocatorEdit;
