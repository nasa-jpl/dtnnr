import { Accordion, Anchor, Flex, Loader, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi, Link } from '@tanstack/react-router';
import { useContext } from 'react';
import AuthContext from '../AuthContext';
import { DeleteWarningAlert } from '../components/DeleteWarningAlert';
import DetailsTitle from '../components/DetailsTitle';
import ErrorComponent from '../components/ErrorComponent';
import { ContactTable } from '../contact/ContactTable';
import { formatAllocatedNodeNumbers } from '../utils/formatFunctions';
import {
  operatorContactQuery,
  operatorDetailsQuery as query,
  useAssociateOperatorContactMutation,
  useDeleteOperatorMutation,
  useDissociateOperatorContactMutation,
} from '../utils/queries';
import { AllocatedNodeNumbersUpdate } from './AllocatedNodeNumbersUpdate';
import OperatorEdit from './OperatorEdit';

const route = getRouteApi('/operators/$operatorId');

export function Operator() {
  const { currentUser } = useContext(AuthContext);
  const params = route.useParams();
  const { isPending, isError, data, error } = useQuery(
    query(params.operatorId),
  );
  const deleteRecordMutation = useDeleteOperatorMutation(params.operatorId);
  const operator = data;

  if (isPending) {
    return (
      <Flex justify="center">
        <Loader />
      </Flex>
    );
  }

  if (isError) {
    return <ErrorComponent error={error} />;
  }

  const allocatedNodeNumbers = formatAllocatedNodeNumbers(
    operator.allocated_node_numbers,
  );

  // TODO: API will not include hosts and nodes in representation.
  // We'll eventually have something like /hosts?filter=operator_id={operator_id}
  // to have these relations.

  // operator.hosts is an Array of objects
  const listHosts = operator.hosts.map((h) => (
    <li key={h.host_id}>
      <Anchor component={Link} to={`/hosts/${h.host_id}`}>
        [{h.host_id}] {h.hostname}
      </Anchor>
    </li>
  ));

  // operator.nodes is an Array of objects
  // TODO: order these by node_number
  const listNodes = operator.nodes.map((n) => (
    <li key={n.node_id}>
      <Anchor component={Link} to={`/nodes/${n.node_id}`}>
        ({operator.allocator.allocator_id}, {n.node_number})
      </Anchor>
    </li>
  ));

  return (
    <>
      <DetailsTitle
        name="Operator"
        editModalTitle="Edit operator"
        handleEditRecordModal={(closeModals) => (
          <OperatorEdit initialOperator={operator} closeModals={closeModals} />
        )}
        deleteModalTitle="Delete operator"
        deleteModalDescription={
          <>
            <Text size="sm">
              Are you sure you want to delete operator ID {operator.operator_id}
              ? This action is destructive and cannot be undone.
            </Text>
            <DeleteWarningAlert
              text={
                <Text size="sm" mb="sm">
                  Deletion will set operator_id to null in associated hosts and
                  nodes.
                </Text>
              }
              contactParentName="operator"
              mt="md"
            />
          </>
        }
        confirmDeleteMessage="Delete operator"
        record={operator}
        deleteRecordMutation={deleteRecordMutation}
      />
      <p>
        <b>Operator ID: </b>
        {operator.operator_id}
        <br />
        <b>Operator name: </b>
        <span className="show-white-space">{operator.operator_name}</span>
        <br />
        <b>Allocator: </b>
        <Anchor
          component={Link}
          to={`/allocators/${operator.allocator.allocator_id}`}
          className="show-white-space"
        >
          [{operator.allocator.allocator_id}]{' '}
          {operator.allocator.allocator_name}
        </Anchor>
        <br />
      </p>
      <p>Allocated node numbers: {allocatedNodeNumbers}</p>
      {currentUser && (
        <AllocatedNodeNumbersUpdate operatorId={operator.operator_id} />
      )}
      <Accordion multiple={true} defaultValue={['Hosts', 'Nodes', 'Contacts']}>
        <Accordion.Item value="Hosts">
          <Accordion.Control>
            <Title order={3}>Hosts</Title>
          </Accordion.Control>
          <Accordion.Panel className="show-white-space">
            {listHosts}
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Nodes">
          <Accordion.Control>
            <Title order={3}>Nodes</Title>
          </Accordion.Control>
          <Accordion.Panel>{listNodes}</Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Contacts">
          <Accordion.Control>
            <Title order={3}>Points of contact</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <ContactTable
              operatorId={operator.operator_id}
              query={operatorContactQuery(operator.operator_id)}
              dissociateMutationToUse={useDissociateOperatorContactMutation}
              dissociateMutationArgs={[params.operatorId]}
              associateMutationToUse={useAssociateOperatorContactMutation}
              associateMutationArgs={[params.operatorId]}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </>
  );
}

export default Operator;
