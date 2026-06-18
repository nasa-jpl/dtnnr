import { createFileRoute } from '@tanstack/react-router';
import Host from '../host/Host';
import { hostDetailsQuery } from '../utils/queries';

export const Route = createFileRoute('/hosts/$hostId')({
  loader: async ({ context: { queryClient }, params }) => {
    queryClient.prefetchQuery(hostDetailsQuery(params.hostId));
  },
  component: Host,
});
