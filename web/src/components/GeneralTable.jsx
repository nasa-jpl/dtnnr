import { Alert, Anchor, Space } from '@mantine/core';
import { useDebouncedState } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import FilterTextInput from '../components/FilterTextInput';
import HomeTable from '../components/HomeTable';
import { formatGeneralError } from '../utils/formatFunctions';
import { generalTableQuery as query } from '../utils/queries';
import { drill } from '../utils/util';
import classes from './GeneralTable.module.css';

// Have to manually keep these updated to match the table's columns
const NUM_COLUMNS = 7;
const FILTER_ACCESSORS = [
  'allocator_id',
  'node_number',
  'operator_name',
  'host_name',
  'num_endpoints',
  'num_inducts',
  'num_outducts',
];

export function GeneralTable() {
  const { isPending, isError, data, error } = useQuery(query);

  const [queries, setQueries] = useDebouncedState(
    Array(NUM_COLUMNS).fill(''),
    200,
  );
  const setQuery = (i, v) => {
    setQueries(Object.assign([...queries], { [i]: v }));
  };
  const [filteredData, setFilteredData] = useState(data);

  useEffect(() => {
    if (!data) {
      setFilteredData([]);
      return;
    }
    setFilteredData(
      data.filter((record) => {
        for (let i = 0; i < queries.length; i++) {
          if (
            queries[i] !== '' &&
            !`${drill(record, FILTER_ACCESSORS[i])}`
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
      initialColumnAccessor="allocator_id"
      filteredData={filteredData}
      dataIsFiltered={data !== filteredData}
      fetching={isPending}
      columns={[
        {
          accessor: 'allocator_id',
          title: 'Allocator ID',
          sortable: true,
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
              description="Show nodes with allocator IDs that include the specified number"
              placeholder="Search allocator IDs..."
              handleSetQuery={setQuery}
              queryIndex={0}
              defaultValue={queries[0]}
            />
          ),
          filtering: queries[0] !== '',
        },
        {
          accessor: 'node_number',
          title: 'Node number',
          sortable: true,
          render: ({ node_id, node_number }) => (
            <Anchor component={Link} size="sm" to={`/nodes/${node_id}`}>
              {node_number}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Node numbers"
              description="Show nodes with node numbers that include the specified number"
              placeholder="Search node numbers..."
              handleSetQuery={setQuery}
              queryIndex={1}
              defaultValue={queries[1]}
            />
          ),
          filtering: queries[1] !== '',
        },
        {
          accessor: 'operator_name',
          title: 'Operator',
          render: ({ operator_id, operator_name }) =>
            !operator_id ? (
              ''
            ) : (
              <Anchor
                component={Link}
                size="sm"
                to={`/operators/${operator_id}`}
                className={`td-string-col ${classes.operatorColumn}`}
              >
                {operator_name}
              </Anchor>
            ),
          filter: (
            <FilterTextInput
              label="Operators"
              description="Show nodes under operators with the specified name"
              placeholder="Search operators..."
              handleSetQuery={setQuery}
              queryIndex={2}
              defaultValue={queries[2]}
            />
          ),
          filtering: queries[2] !== '',
          width: '26%',
        },
        {
          accessor: 'host_name',
          title: 'Host',
          render: ({ host_id, host_name }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/hosts/${host_id}`}
              className={`td-string-col ${classes.hostColumn}`}
            >
              {host_name}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Hosts"
              description="Show nodes under hosts with the specified name"
              placeholder="Search hosts..."
              handleSetQuery={setQuery}
              queryIndex={3}
              defaultValue={queries[3]}
            />
          ),
          filtering: queries[3] !== '',
          width: '26%',
        },
        {
          accessor: 'num_endpoints',
          title: ' No. endpoints',
          sortable: true,
          filter: (
            <FilterTextInput
              label="Number of endpoints"
              description="Show nodes with a number of endpoints that include the specified number"
              placeholder="Search endpoints..."
              handleSetQuery={setQuery}
              queryIndex={4}
              defaultValue={queries[4]}
            />
          ),
          filtering: queries[4] !== '',
        },
        {
          accessor: 'num_inducts',
          title: 'No. inducts',
          sortable: true,
          filter: (
            <FilterTextInput
              label="Number of inducts"
              description="Show nodes with a number of inducts that include the specified number"
              placeholder="Search inducts..."
              handleSetQuery={setQuery}
              queryIndex={5}
              defaultValue={queries[5]}
            />
          ),
          filtering: queries[5] !== '',
        },
        {
          accessor: 'num_outducts',
          title: 'No. outducts',
          sortable: true,
          filter: (
            <FilterTextInput
              label="Number of outducts"
              description="Show nodes with a number of outducts that include the specified number"
              placeholder="Search outducts..."
              handleSetQuery={setQuery}
              queryIndex={6}
              defaultValue={queries[6]}
            />
          ),
          filtering: queries[6] !== '',
        },
      ]}
      idAccessor="node_id"
    />
  );

  return (
    <>
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

export default GeneralTable;
