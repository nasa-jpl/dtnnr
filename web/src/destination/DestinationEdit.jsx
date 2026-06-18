import { useUpdateDestinationMutation } from '../utils/queries';
import DestinationForm from './DestinationForm';

function DestinationEdit({ initialDestination, hostId, closeModals }) {
  return (
    <DestinationForm
      initialDestination={initialDestination}
      hostId={hostId}
      closeModals={closeModals}
      mutation={useUpdateDestinationMutation(
        initialDestination.destination_id,
        hostId,
      )}
      notFoundErrorMessage={`Destination ID ${initialDestination.destination_id}
        does not exist. The record has likely been deleted, refresh the table.`}
      formDescription={`Fill out this form to update the destination identified
        by destination ID ${initialDestination.destination_id}.`}
    />
  );
}

export default DestinationEdit;
