import { createFileRoute } from '@tanstack/react-router';
import { authBeforeLoad } from '../App';
import NodeCreate from '../node/NodeCreate';

export const Route = createFileRoute('/nodes/create')({
  beforeLoad: authBeforeLoad,
  component: NodeCreate,
});
