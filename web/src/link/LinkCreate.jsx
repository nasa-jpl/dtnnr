import { useCreateLinkMutation } from '../utils/queries';
import { LinkForm } from './LinkForm';

export function LinkCreate({ hostId, closeModals }) {
  return (
    <LinkForm
      hostId={hostId}
      closeModals={closeModals}
      mutation={useCreateLinkMutation(hostId)}
      formDescription={`Fill out this form to create a link associated with
        host ID ${hostId}. Keep in mind that links are "local" — create links
        that this particular host has access to.`}
    />
  );
}
