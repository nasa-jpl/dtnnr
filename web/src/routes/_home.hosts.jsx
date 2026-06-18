import { createFileRoute } from '@tanstack/react-router';
import { HostTable } from '../host/HostTable';
import { hostTableQuery } from '../utils/queries';

export const Route = createFileRoute('/_home/hosts')({
  loader: async ({ context: { queryClient } }) => {
    queryClient.prefetchQuery(hostTableQuery);
  },
  component: HostTable,
});
