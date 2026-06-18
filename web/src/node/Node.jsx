import {
  Accordion,
  Anchor,
  Badge,
  Flex,
  Group,
  Loader,
  Text,
  Title,
} from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi, Link } from '@tanstack/react-router';
import { ClProtocolTable } from '../cl_protocol/ClProtocolTable';
import { DeleteWarningAlert } from '../components/DeleteWarningAlert';
import DetailsTitle from '../components/DetailsTitle';
import ErrorComponent from '../components/ErrorComponent';
import { ContactTable } from '../contact/ContactTable';
import { EndpointImcTable } from '../endpoint/EndpointImcTable';
import { EndpointIpnTable } from '../endpoint/EndpointIpnTable';
import { InductTable } from '../induct/InductTable';
import { SeatTable } from '../seat/SeatTable';
import {
  nodeContactQuery,
  nodeDetailsQuery as query,
  useAssociateNodeContactMutation,
  useDeleteNodeMutation,
  useDissociateNodeContactMutation,
} from '../utils/queries';
import { NodeCopy } from './NodeCopy';
import NodeEdit from './NodeEdit';

const route = getRouteApi('/nodes/$nodeId');

export function Node() {
  const params = route.useParams();
  const { isPending, isError, data, error } = useQuery(query(params.nodeId));
  const deleteRecordMutation = useDeleteNodeMutation();
  const node = data;

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

  let FQNN = `(${node.allocator.allocator_id}, ${node.node_number})`;
  let sdr_badges = node.sdr_config_flags?.map((f) => (
    <Badge key={f}>{f}</Badge>
  ));

  return (
    <>
      <DetailsTitle
        name="Node"
        editModalTitle="Edit node"
        handleEditRecordModal={(closeModals) => (
          <NodeEdit initialNode={node} closeModals={closeModals} />
        )}
        copyModalTitle="Copy node"
        handleCopyRecordModal={(closeModals) => (
          <NodeCopy node={node} closeModals={closeModals} />
        )}
        deleteModalTitle="Delete node"
        deleteModalDescription={
          <>
            <Text size="sm">
              Are you sure you want to delete node ID {node.node_id}? This
              action is destructive and cannot be undone.
            </Text>
            <DeleteWarningAlert contactParentName="node" mt="md" />
          </>
        }
        confirmDeleteMessage="Delete node"
        record={node}
        deleteRecordMutation={deleteRecordMutation}
      />
      <p>
        <b>Fully Qualified Node Number: </b>
        <span>{FQNN}</span>
        <br />
        <b>Allocator: </b>
        <Anchor
          component={Link}
          to={`/allocators/${node.allocator.allocator_id}`}
          className="show-white-space"
        >
          [{node.allocator.allocator_id}] {node.allocator.allocator_name}
        </Anchor>
        <br />
        {node.operator && (
          <>
            <b>Operator: </b>
            <Anchor
              component={Link}
              to={`/operators/${node.operator.operator_id}`}
              className="show-white-space"
            >
              [{node.operator.operator_id}] {node.operator.operator_name}
            </Anchor>
            <br />
          </>
        )}
        {node.host && (
          <>
            <b>Host: </b>
            <Anchor
              component={Link}
              to={`/hosts/${node.host.host_id}`}
              className="show-white-space"
            >
              [{node.host.host_id}] {node.host.hostname}
            </Anchor>
            <br />
          </>
        )}
      </p>
      <p style={{ marginBottom: 0 }}>
        <i>Storage information</i>
        <br />
        SDR working memory (byte): {node.sdr_wm_size ?? <i>Omitted</i>}
      </p>
      <span>
        SDR config flags:{' '}
        {node.sdr_config_flags ? (
          <Group gap="0.2rem" display="inline-flex">
            {sdr_badges}
          </Group>
        ) : (
          <i>Omitted</i>
        )}
      </span>
      <p style={{ marginTop: 0 }}>
        Heap words: {node.heap_words ?? <i>Omitted</i>}
        <br />
        Working memory (byte): {node.wm_size ?? <i>Omitted</i>}
        <br />
      </p>
      <p>Node name: {node.node_name ?? <i>N/A</i>}</p>
      <h2>Comments</h2>
      <p className="show-white-space">{node.comments}</p>

      <Accordion
        multiple={true}
        defaultValue={[
          'ipn endpoints',
          'imc endpoints',
          'CL protocols',
          'Inducts',
          'Seats',
          'Contacts',
        ]}
      >
        <Accordion.Item value="ipn endpoints">
          <Accordion.Control>
            <Title order={3}>ipn endpoints</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <EndpointIpnTable nodeId={node.node_id} FQNN={FQNN} />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="imc endpoints">
          <Accordion.Control>
            <Title order={3}>imc endpoints</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <EndpointImcTable nodeId={node.node_id} FQNN={FQNN} />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="CL protocols">
          <Accordion.Control>
            <Title order={3}>CL protocols</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <ClProtocolTable nodeId={node.node_id} FQNN={FQNN} />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Inducts">
          <Accordion.Control>
            <Title order={3}>Inducts</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <InductTable
              nodeId={node.node_id}
              allocatorId={node.allocator.allocator_id}
              nodeNumber={node.node_number}
              hostId={node?.host?.host_id}
              FQNN={FQNN}
            />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Seats">
          <Accordion.Control>
            <Title order={3}>Seats</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <SeatTable
              nodeId={node.node_id}
              hostId={node?.host?.host_id}
              FQNN={FQNN}
            />
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="Contacts">
          <Accordion.Control>
            <Title order={3}>Points of contact</Title>
          </Accordion.Control>
          <Accordion.Panel>
            <ContactTable
              nodeId={node.node_id}
              query={nodeContactQuery(node.node_id)}
              dissociateMutationToUse={useDissociateNodeContactMutation}
              dissociateMutationArgs={[params.nodeId]}
              associateMutationToUse={useAssociateNodeContactMutation}
              associateMutationArgs={[params.nodeId]}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
      <br />
      <Text c="dimmed">
        Created at:{' '}
        <time dateTime={node.created_at}>
          {new Date(node.created_at).toString()}
        </time>
      </Text>
      <Text c="dimmed">
        Modified at:{' '}
        <time dateTime={node.modified_at}>
          {new Date(node.modified_at).toString()}
        </time>
      </Text>
    </>
  );
}

export default Node;
