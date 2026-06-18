import { ActionIcon, Box, Group, Menu, Title, Tooltip } from '@mantine/core';
import { IconEdit } from '@tabler/icons-react';
import { EntityTable, TableActions } from '../components/EntityTable';
import { useDeleteSeatMutation, useSeatQuery } from '../utils/queries';
import { SeatCreate } from './SeatCreate';
import { SeatEdit } from './SeatEdit';
import { SeatLinks } from './SeatLinks';
import { SeatLinksEdit } from './SeatLinksEdit';

export function SeatTable({ nodeId, FQNN, hostId }) {
  return (
    <EntityTable
      result={useSeatQuery(nodeId)}
      deleteRecord={useDeleteSeatMutation(nodeId)}
      fieldIdName="seat_id"
      columnsToShow={[
        {
          accessor: 'seat_id',
          title: 'ID',
          noWrap: true,
          width: '20%',
        },
        {
          accessor: 'lsi_command_full',
          title: 'LSI command',
          noWrap: true,
          width: '80%',
        },
      ]}
      rowExpansionContent={(record) => (
        <Box m="1rem">
          <Title order={6}>Links</Title>
          <SeatLinks seatId={record.seat_id} />
        </Box>
      )}
      createRecordName="Create seat"
      handleCreateRecordModal={(closeModals) => (
        <SeatCreate
          nodeId={nodeId}
          hostId={hostId}
          FQNN={FQNN}
          closeModals={closeModals}
        />
      )}
      renderActions={(record, openModal, closeModal, onDeleteInternal) => (
        <Group gap={4} justify="center" wrap="nowrap">
          <Menu shadow="md" width={150}>
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
                    <SeatEdit
                      initialSeat={record}
                      nodeId={nodeId}
                      hostId={hostId}
                      FQNN={FQNN}
                      closeModals={closeModal}
                    />,
                    { title: 'Edit seat' },
                  );
                }}
              >
                Seat
              </Menu.Item>
              {hostId === undefined && (
                <Tooltip
                  target="#replace-seat-links"
                  label="Cannot add links without host"
                />
              )}
              <Menu.Item
                disabled={hostId === undefined}
                id="replace-seat-links"
                onClick={(e) => {
                  e.stopPropagation();
                  openModal(
                    <SeatLinksEdit
                      seatId={record.seat_id}
                      hostId={hostId}
                      closeModals={closeModal}
                    />,
                    { title: 'Replace seat links' },
                  );
                }}
              >
                Links
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>

          <TableActions
            record={record}
            onDeleteConfirm={onDeleteInternal}
            fieldIdName="seat_id"
          />
        </Group>
      )}
    />
  );
}
