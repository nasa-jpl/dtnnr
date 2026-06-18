import { useCreateEndpointImcMutation } from '../utils/queries';
import { EndpointImcForm } from './EndpointImcForm';

export function EndpointImcCreate({ nodeId, FQNN, closeModals }) {
  return (
    <EndpointImcForm
      closeModals={closeModals}
      nodeId={nodeId}
      mutation={useCreateEndpointImcMutation(nodeId)}
      formDescription={`Fill out this form to create an imc endpoint associated with node ${FQNN}.`}
    />
  );
}
