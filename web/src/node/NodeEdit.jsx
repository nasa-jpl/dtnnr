import { Text } from '@mantine/core';
import { useUpdateNodeMutation } from '../utils/queries';
import NodeForm from './NodeForm';

function NodeEdit({ initialNode, closeModals }) {
  return (
    <NodeForm
      initialNode={initialNode}
      closeModals={closeModals}
      mutation={useUpdateNodeMutation(initialNode.node_id)}
      formDescription={
        <Text c="dimmed" size="sm">
          Fill out this form to update the node identified by node ID{' '}
          {initialNode.node_id}.
        </Text>
      }
      method="PATCH"
    />
  );
}

export default NodeEdit;
