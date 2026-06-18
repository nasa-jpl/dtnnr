import { Accordion, Anchor, Flex, Loader, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import DetailsTitle from '../components/DetailsTitle';
import ErrorComponent from '../components/ErrorComponent';
import { PhoneNumberList } from '../phone_number/PhoneNumberList';
import {
  contactDetailsQuery as query,
  useDeleteContactMutation,
} from '../utils/queries';
import { ContactEdit } from './ContactEdit';

const route = getRouteApi('/contacts/$contactId');

export function Contact() {
  const params = route.useParams();
  const result = useQuery(query(params.contactId));
  const { isPending, isError, data, error } = result;
  const deleteRecordMutation = useDeleteContactMutation();
  const contact = data;

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

  // TODO: API doesn't have an easy way to access these at the moment
  // const listAllocators = contact.allocators.map(a =>
  //   <li key={a.allocator_id}>
  //     <Anchor component={Link} to={`/allocators/${a.allocator_id}`}>{a.allocator_name}</Anchor>
  //   </li>
  // );

  // const listOperators = contact.operators.map(o =>
  //   <li key={o.operator_id}>
  //     <Anchor component={Link} to={`/operators/${o.operator_id}`}>{o.operator_name}</Anchor>
  //   </li>
  // );

  // const listHosts = contact.hosts.map(h =>
  //   <li key={h.host_id}>
  //     <Anchor component={Link} to={`/hosts/${h.host_id}`}>{h.host_name}</Anchor>
  //   </li>
  // );

  // const listNodes = contact.nodes.map(n =>
  //   <li key={n.node_id}>
  //     <Anchor component={Link} to={`/nodes/${n.node_id}`}>
  //       ({n.allocator.allocator_id}, {n.node_number})
  //     </Anchor>
  //   </li>
  // );

  return (
    <>
      <DetailsTitle
        name="Point of contact"
        editModalTitle="Edit point of contact"
        handleEditRecordModal={(closeModals) => (
          <ContactEdit initialContact={contact} closeModals={closeModals} />
        )}
        deleteModalTitle="Delete point of contact"
        deleteModalDescription={
          <Text size="sm">
            Are you sure you want to delete contact ID {contact.contact_id}?
            This action is destructive and cannot be undone.
          </Text>
        }
        confirmDeleteMessage="Delete point of contact"
        record={contact}
        deleteRecordMutation={deleteRecordMutation}
      />
      <p>
        <b>Contact ID: </b>
        {contact.contact_id}
        <br />
        <b>Name: </b>
        <span className="show-white-space">{contact.contact_name}</span>
        <br />
        <b>Email: </b>
        <Anchor className="show-white-space" href={`mailto:${contact.email}`}>
          {contact.email}
        </Anchor>
      </p>
      <Accordion
        multiple={true}
        defaultValue={[
          // 'Allocators',
          // 'Operators',
          // 'Hosts',
          // 'Nodes',
          'Phone numbers',
        ]}
      >
        {/* <Accordion.Item value="Allocators">
          <Accordion.Control>
            <Title order={3}>Allocators</Title>
          </Accordion.Control>
          <Accordion.Panel className="show-white-space">
            {listAllocators}
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Operators">
          <Accordion.Control>
            <Title order={3}>Operators</Title>
          </Accordion.Control>
          <Accordion.Panel className="show-white-space">
            {listOperators}
          </Accordion.Panel>
        </Accordion.Item>

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
          <Accordion.Panel>
            {listNodes}
          </Accordion.Panel>
        </Accordion.Item> */}

        <Accordion.Item value="Phone numbers">
          <Accordion.Control>
            <Title order={3}>Phone numbers</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <PhoneNumberList contactId={contact.contact_id} />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </>
  );
}
