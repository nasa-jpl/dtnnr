import { useCreateDestinationMutation } from '../utils/queries';
import DestinationForm from './DestinationForm';

function DestinationCreate({ hostId, closeModals }) {
  return (
    <DestinationForm
      hostId={hostId}
      closeModals={closeModals}
      mutation={useCreateDestinationMutation(hostId)}
      notFoundErrorMessage={`Host ID ${hostId} does not exist. The host has
        likely been deleted. Refresh the page.`}
      formDescription={`Fill out this form to create a destination associated
        with host ID ${hostId}.`}
    />
  );
}

export default DestinationCreate;
