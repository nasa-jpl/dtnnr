import { useCreateInductMutation } from '../utils/queries';
import { InductForm } from './InductForm';

export function InductCreate({
  nodeId,
  allocatorId,
  nodeNumber,
  hostId,
  FQNN,
  closeModals,
}) {
  return (
    <InductForm
      nodeId={nodeId}
      allocatorId={allocatorId}
      nodeNumber={nodeNumber}
      hostId={hostId}
      mutation={useCreateInductMutation(nodeId)}
      closeModals={closeModals}
      formDescription={`Fill out this form to create an induct
        associated with node ${FQNN}`}
    />
  );
}
