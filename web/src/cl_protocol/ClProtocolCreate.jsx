import { useCreateClProtocolMutation } from '../utils/queries';
import { ClProtocolForm } from './ClProtocolForm';

export function ClProtocolCreate({ nodeId, FQNN, closeModals }) {
  return (
    <ClProtocolForm
      nodeId={nodeId}
      closeModals={closeModals}
      mutation={useCreateClProtocolMutation(nodeId)}
      formDescription={`Fill out this form to create a CL protocol associated
        with node ${FQNN}.`}
    />
  );
}
