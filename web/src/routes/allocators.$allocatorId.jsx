import { createFileRoute } from '@tanstack/react-router';
import Allocator from '../allocator/Allocator';
import { allocatorDetailsQuery } from '../utils/queries';

export const Route = createFileRoute('/allocators/$allocatorId')({
  loader: async ({ context: { queryClient }, params }) => {
    queryClient.prefetchQuery(allocatorDetailsQuery(params.allocatorId));
  },
  component: Allocator,
});
