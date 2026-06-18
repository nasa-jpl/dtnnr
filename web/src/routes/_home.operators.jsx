import { createFileRoute } from '@tanstack/react-router';
import { OperatorTable } from '../operator/OperatorTable';
import { operatorTableQuery } from '../utils/queries';

export const Route = createFileRoute('/_home/operators')({
  loader: async ({ context: { queryClient } }) => {
    queryClient.prefetchQuery(operatorTableQuery);
  },
  component: OperatorTable,
});
