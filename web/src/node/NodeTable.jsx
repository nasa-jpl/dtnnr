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
import { nodeTableQuery as query } from '../utils/queries';
import { drill } from '../utils/util';
import classes from './NodeTable.module.css';

// Have to manually keep these updated to match the table's columns.
// This assumes the number of columns matches the number of columns that can
// be filtered.
const FILTER_ACCESSORS = [
  'allocator.allocator_id',
  'node_number',
  'operator.operator_name',
  'host.hostname',
  'sdr_wm_size',
  'sdr_config_flags',
  'heap_words',
  'wm_size',
];

export function NodeTable() {
  const { currentUser } = useContext(AuthContext);
  const { isPending, isError, data, error } = useQuery(query);

  // We need `queries` at this level instead of at HomeTable.jsx because we need
  // to pass setQuery into FilterTextInput
  // https://stackoverflow.com/a/53906907
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
      data?.items.filter((node) => {
        for (let i = 0; i < queries.length; i++) {
          if (queries[i] === '') {
            continue;
          }
          let string = `${drill(node, FILTER_ACCESSORS[i])}`.toLowerCase();
          if (!string.includes(queries[i].trim().toLowerCase())) {
            return false;
          }
        }
        return true;
      }),
    );
  }, [data, queries]);

  let content = (
    <HomeTable
      initialColumnAccessor="allocator.allocator_id"
      filteredData={filteredData}
      dataIsFiltered={data?.items !== filteredData}
      fetching={isPending}
      columns={[
        {
          accessor: 'allocator.allocator_id',
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
              description="Show nodes with allocator IDs that include the specified number"
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
          accessor: 'node_number',
          title: 'Node number',
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
              queryIndex={FILTER_ACCESSORS.indexOf('node_number')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('node_number')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('node_number')] !== '',
        },
        {
          accessor: 'operator',
          title: 'Operator',
          render: ({ operator }) =>
            !operator ? (
              ''
            ) : (
              <Anchor
                component={Link}
                size="sm"
                to={`/operators/${operator.operator_id}`}
                className={`td-string-col ${classes.operatorColumn}`}
              >
                {operator.operator_name}
              </Anchor>
            ),
          filter: (
            <FilterTextInput
              label="Operators"
              description="Show nodes under operators with the specified name"
              placeholder="Search operators..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('operator.operator_name')}
              defaultValue={
                queries[FILTER_ACCESSORS.indexOf('operator.operator_name')]
              }
            />
          ),
          filtering:
            queries[FILTER_ACCESSORS.indexOf('operator.operator_name')] !== '',
          width: '14%',
        },
        {
          accessor: 'host',
          title: 'Host',
          render: ({ host }) =>
            !host ? (
              ''
            ) : (
              <Anchor
                component={Link}
                size="sm"
                to={`/hosts/${host.host_id}`}
                className={`td-string-col ${classes.hostColumn}`}
              >
                {host.hostname}
              </Anchor>
            ),
          filter: (
            <FilterTextInput
              label="Hosts"
              description="Show nodes under hosts with the specified name"
              placeholder="Search hosts..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('host.hostname')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('host.hostname')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('host.hostname')] !== '',
          width: '14%',
        },
        {
          accessor: 'sdr_wm_size',
          title: 'SDR working memory',
          filter: (
            <FilterTextInput
              label="SDR working memory sizes"
              description="Show nodes with SDR working memory sizes that include the specified number"
              placeholder="Search SDR working memory sizes..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('sdr_wm_size')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('sdr_wm_size')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('sdr_wm_size')] !== '',
        },
        {
          accessor: 'sdr_config_flags',
          title: 'SDR config flags',
          render: ({ sdr_config_flags }) =>
            !sdr_config_flags ? '' : sdr_config_flags.join(', '),
          // TODO: improve this with a TagsInput or PillsInput
          filter: (
            <FilterTextInput
              label="SDR config flags"
              description="Show nodes with SDR config flags that include the specified string"
              placeholder="Search SDR config flags..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('sdr_config_flags')}
              defaultValue={
                queries[FILTER_ACCESSORS.indexOf('sdr_config_flags')]
              }
            />
          ),
          filtering:
            queries[FILTER_ACCESSORS.indexOf('sdr_config_flags')] !== '',
        },
        {
          accessor: 'heap_words',
          title: 'Heap words',
          filter: (
            <FilterTextInput
              label="Heap words"
              description="Show nodes with heap words that include the specified number"
              placeholder="Search heap words..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('heap_words')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('heap_words')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('heap_words')] !== '',
        },
        {
          accessor: 'wm_size',
          title: 'Working memory',
          filter: (
            <FilterTextInput
              label="Working memory sizes"
              description="Show nodes with working memory sizes that include the specified number"
              placeholder="Search working memory sizes..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('wm_size')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('wm_size')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('wm_size')] !== '',
        },
      ]}
      idAccessor="node_id"
    />
  );

  return (
    <>
      <Group justify="space-between">
        <Text size="xl" fw={700}>
          Nodes
        </Text>
        {currentUser && (
          <NewButton component={Link} to={`/nodes/create`}>
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

export default NodeTable;
