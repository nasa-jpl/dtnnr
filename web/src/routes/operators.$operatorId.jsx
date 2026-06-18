import { createFileRoute } from '@tanstack/react-router';
import Operator from '../operator/Operator';
import { operatorDetailsQuery } from '../utils/queries';

export const Route = createFileRoute('/operators/$operatorId')({
  loader: async ({ context: { queryClient }, params }) => {
    queryClient.prefetchQuery(operatorDetailsQuery(params.operatorId));
  },
  component: Operator,
});
