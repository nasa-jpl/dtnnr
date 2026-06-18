import { Text } from '@mantine/core';
import { useUpdateOperatorMutation } from '../utils/queries';
import OperatorForm from './OperatorForm';

function OperatorEdit({ initialOperator, closeModals }) {
  return (
    <OperatorForm
      initialOperator={initialOperator}
      closeModals={closeModals}
      mutation={useUpdateOperatorMutation(initialOperator.operator_id)}
      formDescription={
        <Text c="dimmed" size="sm">
          Fill out this form to update the host identified by operator ID{' '}
          {initialOperator.operator_id}.
        </Text>
      }
      method="PATCH"
    />
  );
}

export default OperatorEdit;
