import { Alert, Anchor, Group, Space, Text } from '@mantine/core';
import { useDebouncedState } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { useContext, useEffect, useState } from 'react';
import AuthContext from '../AuthContext';
import FilterTextInput from '../components/FilterTextInput';
import HomeTable from '../components/HomeTable';
import { NewButton } from '../components/NewButton';
import { formatGeneralError } from '../utils/formatFunctions';
import { allocatorTableQuery as query } from '../utils/queries';
import { drill } from '../utils/util';
import classes from './AllocatorTable.module.css';

// Have to manually keep these updated to match the table's columns.
// This assumes the number of columns matches the number of columns that can
// be filtered.
const FILTER_ACCESSORS = [
  'allocator_id',
  'allocator_name',
  // 'operators.length',
  // 'nodes.length',
  // 'contacts.length'
];

export function AllocatorTable() {
  const { currentUser } = useContext(AuthContext);
  const { isPending, isError, data, error } = useQuery(query);
  const [queries, setQueries] = useDebouncedState(
    Array(FILTER_ACCESSORS.length).fill(''),
    200,
  );
  const setQuery = (i, v) => {
    setQueries(Object.assign([...queries], { [i]: v }));
  };
  const [filteredData, setFilteredData] = useState(data?.items);

  useEffect(() => {
    if (!data?.items) {
      setFilteredData([]);
      return;
    }
    setFilteredData(
      data?.items.filter((allocator) => {
        for (let i = 0; i < queries.length; i++) {
          if (
            queries[i] !== '' &&
            !`${drill(allocator, FILTER_ACCESSORS[i])}`.includes(
              queries[i].trim().toLowerCase(),
            )
          ) {
            return false;
          }
        }
        return true;
      }),
    );
  }, [data, queries]);

  let content = (
    <HomeTable
      initialColumnAccessor="allocator_id"
      filteredData={filteredData}
      dataIsFiltered={data?.items !== filteredData}
      fetching={isPending}
      columns={[
        {
          accessor: 'allocator_id',
          title: 'Allocator ID',
          render: ({ allocator_id }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/allocators/${allocator_id}`}
            >
              {allocator_id}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Allocator IDs"
              description="Show allocators with an ID that includes the specified number"
              placeholder="Search allocator IDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('allocator_id')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('allocator_id')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('allocator_id')] !== '',
          wtidth: '35%',
        },
        {
          accessor: 'allocator_name',
          title: 'Name',
          render: ({ allocator_id, allocator_name }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/allocators/${allocator_id}`}
              className={`td-string-col ${classes.nameColumn}`}
            >
              {allocator_name}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Allocator names"
              description="Show allocators with the specified name"
              placeholder="Search allocator names..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('allocator_name')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('allocator_name')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('allocator_name')] !== '',
        },
        // {
        //   accessor: 'operators.length',
        //   title: 'No. Operators',
        //   sortable: true,
        //   filter: <FilterTextInput
        //     label="Number of operators"
        //     description="Show allocators with a number of operators that include the specified number"
        //     placeholder="Search operators..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('operators.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('operators.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('operators.length')] !== '',
        // },
        // {
        //   accessor: 'nodes.length',
        //   title: 'No. Nodes',
        //   sortable: true,
        //   filter: <FilterTextInput
        //     label="Number of nodes"
        //     description="Show allocators with a number of nodes that include the specified number"
        //     placeholder="Search nodes..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('nodes.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('nodes.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('nodes.length')] !== '',
        // },
        // {
        //   accessor: 'contacts.length',
        //   title: 'No. Points of Contact',
        //   sortable: true,
        //   filter: <FilterTextInput
        //     label="Number of points of contact"
        //     description="Show allocators with a number of points of contact that include the specified number"
        //     placeholder="Search points of contact..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('contacts.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('contacts.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('contacts.length')] !== '',
        // }
      ]}
      idAccessor="allocator_id"
    />
  );

  return (
    <>
      <Group justify="space-between">
        <Text size="xl" fw={700}>
          Allocators
        </Text>
        {currentUser && (
          <NewButton component={Link} to={`/allocators/create`}>
            New
          </NewButton>
        )}
      </Group>
      <Space h="md" />
      {isError && (
        <>
          <Alert color="red" title="Error">
            {formatGeneralError(error)}
          </Alert>
          <Space h="md" />
        </>
      )}
      {content}
    </>
  );
}

export default AllocatorTable;
