import { useUpdateClProtocolMutation } from '../utils/queries';
import { ClProtocolForm } from './ClProtocolForm';

export function ClProtocolEdit({ initialProtocol, nodeId, closeModals }) {
  return (
    <ClProtocolForm
      initialProtocol={initialProtocol}
      nodeId={nodeId}
      closeModals={closeModals}
      mutation={useUpdateClProtocolMutation(
        initialProtocol.cl_protocol_id,
        nodeId,
      )}
      formDescription={`Fill out this form to update the CL protocol identified by
      CL protocol ID ${initialProtocol.cl_protocol_id}.`}
    />
  );
}
