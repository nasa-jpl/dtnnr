import { createFileRoute } from '@tanstack/react-router';
import { authBeforeLoad } from '../App';
import OperatorCreate from '../operator/OperatorCreate';

export const Route = createFileRoute('/operators/create')({
  beforeLoad: authBeforeLoad,
  component: OperatorCreate,
});
