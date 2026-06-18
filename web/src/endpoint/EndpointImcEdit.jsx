import { useUpdateEndpointImcMutation } from '../utils/queries';
import { EndpointImcForm } from './EndpointImcForm';

export function EndpointImcEdit({
  initialEndpoint,
  nodeId,
  imc_uri,
  closeModals,
}) {
  return (
    <EndpointImcForm
      initialEndpoint={initialEndpoint}
      nodeId={nodeId}
      closeModals={closeModals}
      mutation={useUpdateEndpointImcMutation(
        nodeId,
        initialEndpoint.service_number,
      )}
      formDescription={`Fill out this form to update the endpoint identified by the imc EID ${imc_uri}`}
    />
  );
}
