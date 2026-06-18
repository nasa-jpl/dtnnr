import { Alert, Anchor, Group, Space, Text } from '@mantine/core';
import { useDebouncedState } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { useContext, useEffect, useState } from 'react';
import AuthContext from '../AuthContext';
import FilterTextInput from '../components/FilterTextInput';
import HomeTable from '../components/HomeTable';
import { NewButton } from '../components/NewButton';
import {
  formatAllocatedNodeNumbers,
  formatGeneralError,
} from '../utils/formatFunctions';
import { operatorTableQuery as query } from '../utils/queries';
import { drill } from '../utils/util';
import classes from './OperatorTable.module.css';

// Have to manually keep these updated to match the table's columns.
// This assumes the number of columns matches the number of columns that can
// be filtered.
const FILTER_ACCESSORS = [
  'operator_id',
  'operator_name',
  'allocator.allocator_id',
  'allocated_node_numbers',
  // 'hosts.length',
  // 'nodes.length',
  // 'contacts.length'
];

export function OperatorTable() {
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
      data?.items.filter((operator) => {
        for (let i = 0; i < queries.length; i++) {
          if (queries[i] === '') {
            continue;
          }
          if (FILTER_ACCESSORS[i] === 'allocated_node_numbers') {
            return operator.allocated_node_numbers.some((r) => {
              if (r.lower === null) {
                r.lower = 0;
              }
              if (r.upper === null) {
                r.upper = 2 ** 32 - 1;
              }
              let lower = r.bounds[0] === '(' ? r.lower + 1 : r.lower;
              let upper = r.bounds[1] === ']' ? r.upper : r.upper - 1;
              let value = parseInt(queries[i], 10);
              return value >= lower && value <= upper;
            });
          } else if (
            !`${drill(operator, FILTER_ACCESSORS[i])}`
              .toLowerCase()
              .includes(queries[i].trim().toLowerCase())
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
      initialColumnAccessor="operator_id"
      filteredData={filteredData}
      dataIsFiltered={data?.items !== filteredData}
      fetching={isPending}
      columns={[
        {
          accessor: 'operator_id',
          title: 'ID',
          render: ({ operator_id }) => (
            <Anchor component={Link} size="sm" to={`/operators/${operator_id}`}>
              {operator_id}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Operator IDs"
              description="Show operators with an ID that includes the specified number"
              placeholder="Search operator IDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('operator_id')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('operator_id')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('operator_id')] !== '',
        },
        {
          accessor: 'operator_name',
          title: 'Name',
          render: ({ operator_id, operator_name }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/operators/${operator_id}`}
              className={`td-string-col ${classes.nameColumn}`}
            >
              {operator_name}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Operator names"
              description="Show operators with the specified name"
              placeholder="Search operator names..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('operator_name')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('operator_name')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('operator_name')] !== '',
          width: '20%',
        },
        {
          accessor: 'allocator_id',
          title: 'Allocator ID',
          render: ({ allocator }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/allocators/${allocator.allocator_id}`}
            >
              {allocator.allocator_id}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Allocator IDs"
              description="Show operators under allocator IDs that include the specified number"
              placeholder="Search allocator IDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('allocator.allocator_id')}
              defaultValue={
                queries[FILTER_ACCESSORS.indexOf('allocator.allocator_id')]
              }
            />
          ),
          filtering:
            queries[FILTER_ACCESSORS.indexOf('allocator.allocator_id')] !== '',
        },
        {
          accessor: 'allocated_node_numbers',
          title: 'Allocated node numbers',
          render: ({ allocated_node_numbers }) =>
            formatAllocatedNodeNumbers(allocated_node_numbers),
          filter: (
            <FilterTextInput
              label="Allocated node numbers"
              description="Show operators with a range of allocated numbers that include the specified number"
              placeholder="Search allocator IDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('allocated_node_numbers')}
              defaultValue={
                queries[FILTER_ACCESSORS.indexOf('allocated_node_numbers')]
              }
            />
          ),
          filtering:
            queries[FILTER_ACCESSORS.indexOf('allocated_node_numbers')] !== '',
          width: '35%',
        },
        // {
        //   accessor: 'hosts.length',
        //   title: 'No. Hosts',
        //   filter: <FilterTextInput
        //     label="Number of hosts"
        //     description="Show operators with a number of hosts that include the specified number"
        //     placeholder="Search hosts..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('hosts.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('hosts.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('hosts.length')] !== ''
        // },
        // {
        //   accessor: 'nodes.length',
        //   title: 'No. Nodes',
        //   filter: <FilterTextInput
        //     label="Number of nodes"
        //     description="Show operators with a number of nodes that include the specified number"
        //     placeholder="Search nodes..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('nodes.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('nodes.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('nodes.length')] !== ''
        // },
        // {
        //   accessor: 'contacts.length',
        //   title: 'No. Points of Contact',
        //   filter: <FilterTextInput
        //     label="Number of points of contact"
        //     description="Show operators with a number of points of contact that include the specified number"
        //     placeholder="Search points of contact..."
        //     handleSetQuery={setQuery}
        //     queryIndex={FILTER_ACCESSORS.indexOf('contacts.length')}
        //     defaultValue={queries[FILTER_ACCESSORS.indexOf('contacts.length')]}
        //   />,
        //   filtering: queries[FILTER_ACCESSORS.indexOf('contacts.length')] !== ''
        // }
      ]}
      idAccessor="operator_id"
    />
  );

  return (
    <>
      <Group justify="space-between">
        <Text size="xl" fw={700}>
          Operators
        </Text>
        {currentUser && (
          <NewButton component={Link} to={`/operators/create`}>
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

export default OperatorTable;
