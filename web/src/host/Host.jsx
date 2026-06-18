import { Accordion, Anchor, Flex, Loader, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi, Link } from '@tanstack/react-router';
import { DeleteWarningAlert } from '../components/DeleteWarningAlert';
import DetailsTitle from '../components/DetailsTitle';
import ErrorComponent from '../components/ErrorComponent';
import { ContactTable } from '../contact/ContactTable';
import { DestinationTable } from '../destination/DestinationTable';
import { LinkTable } from '../link/LinkTable';
import {
  hostContactQuery,
  hostDetailsQuery as query,
  useAssociateHostContactMutation,
  useDeleteHostMutation,
  useDissociateHostContactMutation,
} from '../utils/queries';
import { HostCopy } from './HostCopy';
import HostEdit from './HostEdit';

const route = getRouteApi('/hosts/$hostId');

export function Host() {
  const params = route.useParams();
  const { isPending, isError, data, error } = useQuery(query(params.hostId));
  const deleteRecordMutation = useDeleteHostMutation();
  const host = data;

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

  // TODO: API will not include nodes in host's representation
  const listNodes = host.nodes.map((n) => (
    <li key={n.node_id}>
      <Anchor component={Link} to={`/nodes/${n.node_id}`}>
        ({n.allocator.allocator_id}, {n.node_number})
      </Anchor>
    </li>
  ));

  return (
    <>
      <DetailsTitle
        name="Host"
        editModalTitle="Edit host"
        handleEditRecordModal={(closeModals) => (
          <HostEdit initialHost={host} closeModals={closeModals} />
        )}
        copyModalTitle="Copy host"
        handleCopyRecordModal={(closeModals) => (
          <HostCopy host={host} closeModals={closeModals} />
        )}
        deleteModalTitle="Delete host"
        deleteModalDescription={
          <>
            <Text size="sm">
              Are you sure you want to delete host ID {host.host_id}? This
              action is destructive and cannot be undone.
            </Text>
            <DeleteWarningAlert
              text={
                <Text size="sm" mb="sm">
                  Deletion will set host_id to null and nullify host references
                  (e.g., IP inducts will have null destination_id) in associated
                  nodes.
                </Text>
              }
              contactParentName="host"
              mt="md"
            />
          </>
        }
        confirmDeleteMessage="Delete host"
        record={host}
        deleteRecordMutation={deleteRecordMutation}
      />
      <p>
        <b>Host ID: </b>
        {host.host_id}
        <br />
        <b>Hostname: </b>
        <span className="show-white-space">{host.hostname}</span>
        <br />
        <b>Host description: </b>
        <span className="show-white-space">{host.host_description}</span>
        <br />
        <b>SANA SCID: </b>
        {host.sana_scid}
        <br />
        <b>Operator: </b>
        {host.operator && (
          <span className="show-white-space">
            <Anchor
              component={Link}
              to={`/operators/${host.operator.operator_id}`}
            >
              [{host.operator.operator_id}] {host.operator.operator_name}
            </Anchor>
          </span>
        )}
        <br />
        Word size: {host.word_size}
        <br />
        Newline: {host.newline}
      </p>

      <Accordion
        multiple={true}
        defaultValue={['Nodes', 'Destinations', 'Links', 'Contacts']}
      >
        <Accordion.Item value="Nodes">
          <Accordion.Control>
            <Title order={3}>Nodes</Title>
          </Accordion.Control>
          <Accordion.Panel>{listNodes}</Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Destinations">
          <Accordion.Control>
            <Title order={3}>Destinations</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <DestinationTable hostId={host.host_id} />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Links">
          <Accordion.Control>
            <Title order={3}>Links</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <LinkTable hostId={host.host_id} />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Contacts">
          <Accordion.Control>
            <Title order={3}>Points of contact</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <ContactTable
              hostId={host.host_id}
              query={hostContactQuery(host.host_id)}
              dissociateMutationToUse={useDissociateHostContactMutation}
              dissociateMutationArgs={[params.hostId]}
              associateMutationToUse={useAssociateHostContactMutation}
              associateMutationArgs={[params.hostId]}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </>
  );
}

export default Host;
