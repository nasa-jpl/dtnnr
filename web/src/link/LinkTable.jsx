import { EntityTable } from '../components/EntityTable';
import { useDeleteLinkMutation, useLinkQuery } from '../utils/queries';
import { LinkCreate } from './LinkCreate';
import { LinkEdit } from './LinkEdit';

export function LinkTable({ hostId }) {
  return (
    <EntityTable
      result={useLinkQuery(hostId)}
      deleteRecord={useDeleteLinkMutation(hostId)}
      fieldIdName="link_id"
      columnsToShow={[
        {
          accessor: 'link_id',
          title: 'ID',
          width: '15%',
          noWrap: true,
        },
        {
          accessor: 'direction',
          title: 'Direction',
          width: '20%',
        },
        {
          accessor: 'underlying_communication_services',
          title: 'Underlying communication services',
          width: '40%',
          render: ({ underlying_communication_services }) =>
            !underlying_communication_services
              ? ''
              : underlying_communication_services
                  .map((s) => s.underlying_communication_service_name)
                  .join(', '),
        },
        {
          accessor: 'link_rf.band.band_name',
          title: 'Band',
          width: '15%',
        },
      ]}
      // TODO: rowExpansionContent; if there's an endpoint to easily retrieve
      // seats and inducts that use this link, we can render a list here.
      createRecordName="Create link"
      handleCreateRecordModal={(closeModals) => (
        <LinkCreate hostId={hostId} closeModals={closeModals} />
      )}
      onEdit={(record, openModal, closeModal) =>
        openModal(
          <LinkEdit
            initialLink={record}
            hostId={hostId}
            closeModals={closeModal}
          />,
          { title: 'Edit link' },
        )
      }
    />
  );
}
