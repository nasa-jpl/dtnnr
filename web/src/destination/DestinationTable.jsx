import { EntityTable } from '../components/EntityTable';
import {
  useDeleteDestinationMutation,
  useDestinationQuery,
} from '../utils/queries';
import DestinationCreate from './DestinationCreate';
import DestinationEdit from './DestinationEdit';

export function DestinationTable({ hostId }) {
  return (
    <EntityTable
      result={useDestinationQuery(hostId)}
      deleteRecord={useDeleteDestinationMutation(hostId)}
      fieldIdName={'destination_id'}
      columnsToShow={[
        {
          accessor: 'destination_id',
          title: 'ID',
          width: '30%',
          noWrap: true,
        },
        {
          accessor: 'destination_value',
          title: 'Destination',
          width: '60%',
        },
      ]}
      // TODO: separate component to handle this with its own fetch logic
      // since inducts aren't in the destination's representation anymore
      // rowExpansionContent={(record) => (
      //   <>
      //     {record.ip_inducts.length > 0 ? (
      //       <ul>
      //         {record.ip_inducts.map((ip_induct) => {
      //           return (
      //             <li key={ip_induct.induct_id}>
      //               Induct ID {ip_induct.induct_id}, port{' '}
      //               {ip_induct.port_number}, on node (
      //               {ip_induct.induct.node.allocator.allocator_id},{' '}
      //               {ip_induct.induct.node.node_number})
      //             </li>
      //           );
      //         })}
      //       </ul>
      //     ) : (
      //       <>No inducts use {record.ip_address}</>
      //     )}
      //   </>
      // )}
      createRecordName="Create destination"
      handleCreateRecordModal={(closeModals) => (
        <DestinationCreate hostId={hostId} closeModals={closeModals} />
      )}
      onEdit={(record, openModal, closeModal) =>
        openModal(
          <DestinationEdit
            initialDestination={record}
            hostId={hostId}
            closeModals={closeModal}
          />,
          { title: 'Edit destination' },
        )
      }
    />
  );
}
