import { useUpdateEndpointIpnMutation } from '../utils/queries';
import { EndpointIpnForm } from './EndpointIpnForm';

export function EndpointIpnEdit({
  initialEndpoint,
  nodeId,
  ipn_uri,
  closeModals,
}) {
  return (
    <EndpointIpnForm
      initialEndpoint={initialEndpoint}
      nodeId={nodeId}
      closeModals={closeModals}
      mutation={useUpdateEndpointIpnMutation(
        nodeId,
        initialEndpoint.service_number,
      )}
      formDescription={`Fill out this form to update the endpoint identified by the ipn EID ${ipn_uri}`}
    />
  );
}
