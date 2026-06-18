import { createFileRoute } from '@tanstack/react-router';
import { NodeTable } from '../node/NodeTable';
import { nodeTableQuery } from '../utils/queries';

export const Route = createFileRoute('/_home/nodes')({
  loader: async ({ context: { queryClient } }) => {
    queryClient.prefetchQuery(nodeTableQuery);
  },
  component: NodeTable,
});
