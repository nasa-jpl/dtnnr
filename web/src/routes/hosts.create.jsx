import { createFileRoute } from '@tanstack/react-router';
import { authBeforeLoad } from '../App';
import HostCreate from '../host/HostCreate';

export const Route = createFileRoute('/hosts/create')({
  beforeLoad: authBeforeLoad,
  component: HostCreate,
});
