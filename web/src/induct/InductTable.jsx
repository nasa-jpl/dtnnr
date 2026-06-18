import {
  Accordion,
  ActionIcon,
  Box,
  Group,
  Menu,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconCheck, IconEdit } from '@tabler/icons-react';
import { EntityTable, TableActions } from '../components/EntityTable';
import { useDeleteInductMutation, useInductQuery } from '../utils/queries';
import { InductCreate } from './InductCreate';
import { InductEdit } from './InductEdit';
import { InductLinks } from './InductLinks';
import { InductLinksEdit } from './InductLinksEdit';
import { InductSeats } from './InductSeats';
import { InductSeatsEdit } from './InductSeatsEdit';

export function InductTable({ nodeId, allocatorId, nodeNumber, FQNN, hostId }) {
  return (
    <EntityTable
      result={useInductQuery(nodeId)}
      deleteRecord={useDeleteInductMutation(nodeId)}
      fieldIdName="induct_id"
      columnsToShow={[
        {
          accessor: 'induct_id',
          title: 'ID',
          noWrap: true,
          width: '20%',
        },
        {
          // TODO: maybe include ID?
          accessor: 'cl_protocol.cl_protocol_name',
          title: 'CL Protocol',
          noWrap: true,
          width: '20%',
        },
        {
          accessor: 'duct_name.value',
          title: 'Duct Name',
          noWrap: true,
          width: '30%',
        },
        {
          accessor: 'cli_command',
          title: 'CLI Command',
          noWrap: true,
          width: '25%',
        },
        {
          accessor: 'uses_ltp',
          title: 'LTP',
          render: ({ uses_ltp }) =>
            uses_ltp && <IconCheck className="icon-16-px" />,
          width: '5%',
        },
      ]}
      rowExpansionContent={(record) => (
        <Box m="1rem">
          {record.cl_protocol ? (
            <div>CL protocol ID: {record.cl_protocol.cl_protocol_id}</div>
          ) : (
            <div>Not using a CL protocol</div>
          )}
          <Accordion multiple={true} defaultValue={['Links', 'Seats']}>
            {hostId !== undefined && !record.uses_ltp && (
              <Accordion.Item value="Links">
                <Accordion.Control>
                  <Title order={6}>Links</Title>
                </Accordion.Control>
                <Accordion.Panel>
                  <InductLinks inductId={record.induct_id} />
                </Accordion.Panel>
              </Accordion.Item>
            )}
            {record.uses_ltp && (
              <Accordion.Item value="Seats">
                <Accordion.Control>
                  <Title order={6}>Seats</Title>
                </Accordion.Control>
                <Accordion.Panel>
                  <InductSeats inductId={record.induct_id} />
                </Accordion.Panel>
              </Accordion.Item>
            )}
          </Accordion>
        </Box>
      )}
      createRecordName="Create Induct"
      handleCreateRecordModal={(closeModals) => (
        <InductCreate
          nodeId={nodeId}
          allocatorId={allocatorId}
          nodeNumber={nodeNumber}
          hostId={hostId}
          FQNN={FQNN}
          closeModals={closeModals}
        />
      )}
      renderActions={(record, openModal, closeModal, onDeleteInternal) => (
        <Group gap={4} justify="center" wrap="nowrap">
          <Menu shadow="md" width={150} withinPortal>
            <Menu.Target>
              <ActionIcon
                size="md"
                variant="subtle"
                onClick={(e) => e.stopPropagation()}
              >
                <IconEdit className="icon-16-px" />
              </ActionIcon>
            </Menu.Target>

            <Menu.Dropdown>
              <Menu.Item
                onClick={(e) => {
                  e.stopPropagation();
                  openModal(
                    <InductEdit
                      initialInduct={record}
                      nodeId={nodeId}
                      allocatorId={allocatorId}
                      nodeNumber={nodeNumber}
                      hostId={hostId}
                      closeModals={closeModal}
                    />,
                    { title: 'Edit induct' },
                  );
                }}
              >
                Induct
              </Menu.Item>
              {(hostId === undefined || record.uses_ltp) && (
                <Tooltip
                  target="#replace-induct-links"
                  label="Cannot add links without host or if using LTP"
                />
              )}
              <Menu.Item
                disabled={hostId === undefined || record.uses_ltp}
                id="replace-induct-links"
                onClick={(e) => {
                  e.stopPropagation();
                  openModal(
                    <InductLinksEdit
                      inductId={record.induct_id}
                      hostId={hostId}
                      closeModals={closeModal}
                    />,
                    { title: 'Replace induct links' },
                  );
                }}
              >
                Links
              </Menu.Item>
              {!record.uses_ltp && (
                <Tooltip
                  target="#replace-induct-seats"
                  label="Cannot add seats if not using LTP"
                />
              )}
              <Menu.Item
                disabled={!record.uses_ltp}
                id="replace-induct-seats"
                onClick={(e) => {
                  e.stopPropagation();
                  openModal(
                    <InductSeatsEdit
                      inductId={record.induct_id}
                      nodeId={nodeId}
                      closeModals={closeModal}
                    />,
                    { title: 'Replace induct seats' },
                  );
                }}
              >
                Seats
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>

          <TableActions
            record={record}
            onDeleteConfirm={onDeleteInternal}
            fieldIdName="induct_id"
          />
        </Group>
      )}
    />
  );
}
