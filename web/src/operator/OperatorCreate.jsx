import { Text } from '@mantine/core';
import { useCreateOperatorMutation } from '../utils/queries';
import OperatorForm from './OperatorForm';

function OperatorCreate() {
  return (
    <OperatorForm
      mutation={useCreateOperatorMutation()}
      formTitle="Create operator"
      formDescription={
        <Text c="dimmed" size="sm">
          Please fill out this form to create a new operator. After the operator
          has been created, you will be redirected to the operator's page where
          you can add allocated node numbers and point of contact information.
        </Text>
      }
      method="POST"
    />
  );
}

export default OperatorCreate;
