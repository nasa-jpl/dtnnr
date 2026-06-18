import { Group, Pagination } from '@mantine/core';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { EntityTable } from '../components/EntityTable';
import { useDeleteEndpointImcMutation } from '../utils/queries';
import { EndpointImcCreate } from './EndpointImcCreate';
import { EndpointImcEdit } from './EndpointImcEdit';
import classes from './EndpointTable.module.css';

async function fetchEndpoints(nodeId, pageToken, pageSize) {
  const params = new URLSearchParams({
    ...(pageToken !== undefined && { page_token: pageToken }),
    max_page_size: pageSize,
  });
  const response = await fetch(`/api/nodes/${nodeId}/endpoints/imc?${params}`);
  let result;
  try {
    result = await response.json();
  } catch (_error) {
    throw new Error(
      'Unable to parse response from backend. The backend is likely down.',
    );
  }
  if (!response.ok) {
    throw result;
  }
  return result;
}

export function EndpointImcTable({ nodeId, FQNN }) {
  const [pageSize, setPageSize] = useState(10);
  const [currentPageToken, setCurrentPageToken] = useState(undefined);
  const result = useQuery({
    queryKey: ['nodes', nodeId, 'imc-endpoints', pageSize, currentPageToken],
    queryFn: () => fetchEndpoints(nodeId, currentPageToken, pageSize),
    placeholderData: keepPreviousData,
  });

  // biome-ignore lint/correctness/useExhaustiveDependencies: depends on pageSize
  useEffect(() => {
    setCurrentPageToken(undefined);
  }, [pageSize]);

  return (
    <EntityTable
      result={result}
      deleteRecord={useDeleteEndpointImcMutation(nodeId)}
      fieldIdName="uri"
      columnsToShow={[
        {
          accessor: 'uri',
          title: 'imc EID',
          noWrap: true,
          width: '45%',
        },
        {
          accessor: 'disposition',
          title: 'Disposition',
          width: '10%',
        },
        {
          accessor: 'application',
          title: 'Application',
          render: ({ application }) => (
            <div className={`${classes.tdCol} ${classes.application}`}>
              {application}
            </div>
          ),
          width: '45%',
        },
      ]}
      createRecordName="Create imc endpoint"
      handleCreateRecordModal={(closeModals) => (
        <EndpointImcCreate
          nodeId={nodeId}
          FQNN={FQNN}
          closeModals={closeModals}
        />
      )}
      onEdit={(record, openModal, closeModal) =>
        openModal(
          <EndpointImcEdit
            initialEndpoint={record}
            nodeId={nodeId}
            imc_uri={record.uri}
            closeModals={closeModal}
          />,
          {
            title: 'Edit imc endpoint',
          },
        )
      }
      recordsPerPage={pageSize}
      page={1}
      onPageChange={() => {}}
      recordsPerPageOptions={[10, 25, 50, 100]}
      onRecordsPerPageChange={setPageSize}
      renderPagination={({ Controls }) => (
        <>
          <Controls.PageSizeSelector />
          <Pagination.Root>
            <Group>
              <Pagination.First
                disabled={
                  currentPageToken === undefined ||
                  !result?.data?.prev_page_token
                }
                onClick={() => setCurrentPageToken(undefined)}
              />
              <Pagination.Previous
                disabled={!result?.data?.prev_page_token}
                onClick={() => setCurrentPageToken(result.data.prev_page_token)}
              />
              <Pagination.Next
                disabled={!result?.data?.next_page_token}
                onClick={() => setCurrentPageToken(result.data.next_page_token)}
              />
              <Pagination.Last
                disabled={!result?.data?.next_page_token}
                onClick={() => setCurrentPageToken('last')}
              />
            </Group>
          </Pagination.Root>
        </>
      )}
    />
  );
}
