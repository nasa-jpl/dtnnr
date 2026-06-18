import { Accordion, Anchor, Flex, Loader, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi, Link } from '@tanstack/react-router';
import { DeleteWarningAlert } from '../components/DeleteWarningAlert';
import DetailsTitle from '../components/DetailsTitle';
import ErrorComponent from '../components/ErrorComponent';
import { ContactTable } from '../contact/ContactTable';
import {
  allocatorContactQuery,
  allocatorDetailsQuery as query,
  useAssociateAllocatorContactMutation,
  useDeleteAllocatorMutation,
  useDissociateAllocatorContactMutation,
} from '../utils/queries';
import AllocatorEdit from './AllocatorEdit';

const route = getRouteApi('/allocators/$allocatorId');

export function Allocator() {
  const params = route.useParams();
  const { isPending, isError, data, error } = useQuery(
    query(params.allocatorId),
  );
  const deleteRecordMutation = useDeleteAllocatorMutation(params.allocatorId);
  const allocator = data;

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

  // TODO: we'll eventaully have /operators?filter=allocator_id={allocator_id}
  // which is how these things should be rendered

  // allocator.operators is an Array of objects
  // TODO: order these by the lower bounds
  const listOperators = allocator.operators.map((o) => (
    <li key={o.operator_id}>
      <Anchor component={Link} to={`/operators/${o.operator_id}`}>
        [{o.operator_id}] {o.operator_name}
      </Anchor>
      {/* TODO: include allocated node numbers here. We could just represent
       it all in set notation, for each item in operators.allocated_node_numbers,
       `${bounds[0]}${lower}, ${upper}${bounds[1]}` and join them with the
       union symbol. */}
    </li>
  ));

  // allocators.nodes is an Array of objects
  // TODO: order these by node_number
  const listNodes = allocator.nodes.map((n) => (
    <li key={n.node_id}>
      <Anchor component={Link} to={`/nodes/${n.node_id}`}>
        ({allocator.allocator_id}, {n.node_number})
      </Anchor>
    </li>
  ));

  return (
    <>
      <DetailsTitle
        name="Allocator"
        editModalTitle="Edit allocator"
        handleEditRecordModal={(closeModals) => (
          <AllocatorEdit
            initialAllocator={allocator}
            closeModals={closeModals}
          />
        )}
        deleteModalTitle="Delete allocator"
        deleteModalDescription={
          <>
            <Text size="sm">
              Are you sure you want to delete allocator ID{' '}
              {allocator.allocator_id}? This action is destructive and cannot be
              undone.
            </Text>
            <Text size="sm" mt="sm">
              Deletion is restricted if the allocator is still associated with
              operators or nodes.
            </Text>
            <DeleteWarningAlert contactParentName="allocator" mt="md" />
          </>
        }
        confirmDeleteMessage="Delete allocator"
        record={allocator}
        deleteRecordMutation={deleteRecordMutation}
      />
      <p>
        <b>Allocator ID: </b>
        {allocator.allocator_id}
        <br />
        <b>Allocator Name: </b>
        <span className="show-white-space">{allocator.allocator_name}</span>
      </p>

      <Accordion
        multiple={true}
        defaultValue={['Operators', 'Nodes', 'Contacts']}
      >
        <Accordion.Item value="Operators">
          <Accordion.Control>
            <Title order={3}>Operators</Title>
          </Accordion.Control>
          <Accordion.Panel className="show-white-space">
            {listOperators}
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
              allocatorId={allocator.allocator_id}
              query={allocatorContactQuery(allocator.allocator_id)}
              dissociateMutationToUse={useDissociateAllocatorContactMutation}
              dissociateMutationArgs={[params.allocatorId]}
              associateMutationToUse={useAssociateAllocatorContactMutation}
              associateMutationArgs={[params.allocatorId]}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </>
  );
}

export default Allocator;
