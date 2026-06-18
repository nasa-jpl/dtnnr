import { useUpdateContactMutation } from '../utils/queries';
import { ContactForm } from './ContactForm';

export function ContactEdit({ initialContact, closeModals }) {
  return (
    <ContactForm
      initialContact={initialContact}
      closeModals={closeModals}
      mutation={useUpdateContactMutation(initialContact.contact_id)}
      formDescription={`Fill out this form to update the point of contact identified by ID
      ${initialContact.contact_id}.`}
    />
  );
}
