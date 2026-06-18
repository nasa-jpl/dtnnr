import { useCreateSeatMutation } from '../utils/queries';
import { SeatForm } from './SeatForm';

export function SeatCreate({ nodeId, hostId, FQNN, closeModals }) {
  return (
    <SeatForm
      nodeId={nodeId}
      hostId={hostId}
      mutation={useCreateSeatMutation(nodeId)}
      closeModals={closeModals}
      formDescription={`Fill out this form to create a seat
        associated with node ${FQNN}`}
    />
  );
}
