import { createFileRoute } from '@tanstack/react-router';
import Node from '../node/Node';
import { nodeDetailsQuery } from '../utils/queries';

export const Route = createFileRoute('/nodes/$nodeId')({
  loader: async ({ context: { queryClient }, params }) => {
    queryClient.prefetchQuery(nodeDetailsQuery(params.nodeId));
  },
  component: Node,
});
