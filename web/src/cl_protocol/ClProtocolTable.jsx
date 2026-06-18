import { EntityTable } from '../components/EntityTable';
import {
  useClProtocolQuery,
  useDeleteClProtocolMutation,
} from '../utils/queries';
import { ClProtocolCreate } from './ClProtocolCreate';
import { ClProtocolEdit } from './ClProtocolEdit';

export function ClProtocolTable({ nodeId, FQNN }) {
  return (
    <EntityTable
      result={useClProtocolQuery(nodeId)}
      deleteRecord={useDeleteClProtocolMutation(nodeId)}
      fieldIdName="cl_protocol_id"
      columnsToShow={[
        {
          accessor: 'cl_protocol_id',
          title: 'ID',
          width: '15%',
          noWrap: true,
        },
        {
          accessor: 'cl_protocol_name',
          title: 'CL Protocol',
          width: '45%',
        },
        {
          accessor: 'cl_protocol_class',
          title: 'Protocol class',
          render: ({ cl_protocol_class }) => {
            let classes = [];
            if (cl_protocol_class.includes('BP_BEST_EFFORT')) {
              classes.push('Best-effort');
            }
            if (cl_protocol_class.includes('BP_RELIABLE')) {
              classes.push('Reliable');
            }
            return classes.join(', ');
          },
          width: '30%',
        },
      ]}
      // TODO: show inducts that use this CL protocol
      // rowExpansionContent={(record) => {}}
      createRecordName="Create CL protocol"
      handleCreateRecordModal={(closeModals) => (
        <ClProtocolCreate
          nodeId={nodeId}
          FQNN={FQNN}
          closeModals={closeModals}
        />
      )}
      onEdit={(record, openModal, closeModal) =>
        openModal(
          <ClProtocolEdit
            initialProtocol={record}
            nodeId={nodeId}
            closeModals={closeModal}
          />,
          { title: 'Edit CL protocol' },
        )
      }
    />
  );
}
