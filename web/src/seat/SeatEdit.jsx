import { useReplaceSeatMutation } from '../utils/queries';
import { SeatForm } from './SeatForm';

export function SeatEdit({ initialSeat, nodeId, hostId, closeModals }) {
  return (
    <SeatForm
      initialSeat={initialSeat}
      nodeId={nodeId}
      hostId={hostId}
      mutation={useReplaceSeatMutation(nodeId)}
      closeModals={closeModals}
      formDescription={`Fill out this form to update the seat
        identified by seat ID ${initialSeat.seat_id}`}
    />
  );
}
