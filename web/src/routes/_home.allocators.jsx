import { createFileRoute } from '@tanstack/react-router';
import { AllocatorTable } from '../allocator/AllocatorTable';
import { allocatorTableQuery } from '../utils/queries';

export const Route = createFileRoute('/_home/allocators')({
  loader: async ({ context: { queryClient } }) => {
    queryClient.prefetchQuery(allocatorTableQuery);
  },
  component: AllocatorTable,
});
