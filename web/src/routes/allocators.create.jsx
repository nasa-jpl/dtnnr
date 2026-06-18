import { createFileRoute } from '@tanstack/react-router';
import { authBeforeLoad } from '../App';
import AllocatorCreate from '../allocator/AllocatorCreate';

export const Route = createFileRoute('/allocators/create')({
  beforeLoad: authBeforeLoad,
  component: AllocatorCreate,
});
