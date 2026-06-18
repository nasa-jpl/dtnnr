import { useUpdateLinkMutation } from '../utils/queries';
import { LinkForm } from './LinkForm';

export function LinkEdit({ initialLink, hostId, closeModals }) {
  return (
    <LinkForm
      initialLink={initialLink}
      hostId={hostId}
      closeModals={closeModals}
      mutation={useUpdateLinkMutation(initialLink.link_id, hostId)}
      formDescription={`Fill out this form to update the link identified by
        link ID ${initialLink.link_id}.`}
    />
  );
}
