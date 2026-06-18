import { useReplaceInductMutation } from '../utils/queries';
import { InductForm } from './InductForm';

export function InductEdit({
  initialInduct,
  nodeId,
  allocatorId,
  nodeNumber,
  hostId,
  closeModals,
}) {
  return (
    <InductForm
      initialInduct={initialInduct}
      nodeId={nodeId}
      allocatorId={allocatorId}
      nodeNumber={nodeNumber}
      hostId={hostId}
      mutation={useReplaceInductMutation(initialInduct.induct_id, nodeId)}
      closeModals={closeModals}
      formDescription={`Fill out this form to update the induct
        identified by induct ID ${initialInduct.induct_id}`}
    />
  );
}
