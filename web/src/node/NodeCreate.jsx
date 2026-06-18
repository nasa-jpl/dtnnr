import { Text } from '@mantine/core';
import { useCreateNodeMutation } from '../utils/queries';
import NodeForm from './NodeForm';

function NodeCreate() {
  return (
    <NodeForm
      mutation={useCreateNodeMutation()}
      formTitle="Create node"
      formDescription={
        <Text c="dimmed" size="sm">
          Please fill out this form to create a new node. After the node has
          been created, you will be redirected to the node's page where you can
          add more details such as endpoints and inducts.
        </Text>
      }
      method="POST"
    />
  );
}

export default NodeCreate;
