import { createFileRoute } from '@tanstack/react-router';
import { Contact } from '../contact/Contact';
import { contactDetailsQuery } from '../utils/queries';

export const Route = createFileRoute('/contacts/$contactId')({
  loader: async ({ context: { queryClient }, params }) => {
    queryClient.prefetchQuery(contactDetailsQuery(params.contactId));
  },
  component: Contact,
});
