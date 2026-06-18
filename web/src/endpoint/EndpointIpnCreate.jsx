import { useCreateEndpointIpnMutation } from '../utils/queries';
import { EndpointIpnForm } from './EndpointIpnForm';

export function EndpointIpnCreate({ nodeId, FQNN, closeModals }) {
  return (
    <EndpointIpnForm
      closeModals={closeModals}
      nodeId={nodeId}
      mutation={useCreateEndpointIpnMutation(nodeId)}
      formDescription={`Fill out this form to create an ipn endpoint associated with node ${FQNN}.`}
    />
  );
}
