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
import { hostTableQuery as query } from '../utils/queries';
import { drill } from '../utils/util';
import classes from './HostTable.module.css';

// Have to manually keep these updated to match the table's columns.
// This assumes the number of columns matches the number of columns that can
// be filtered.
const FILTER_ACCESSORS = [
  'host_id',
  'hostname',
  'host_description',
  'sana_scid',
  'operator.operator_name',
  'word_size',
  'newline',
];

export function HostTable() {
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
      data?.items.filter((host) => {
        for (let i = 0; i < queries.length; i++) {
          if (queries[i] === '') {
            continue;
          }
          let string;
          switch (FILTER_ACCESSORS[i]) {
            default:
              string = `${drill(host, FILTER_ACCESSORS[i])}`.toLowerCase();
          }
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
      initialColumnAccessor="host_id"
      filteredData={filteredData}
      dataIsFiltered={data?.items !== filteredData}
      fetching={isPending}
      columns={[
        {
          accessor: 'host_id',
          title: 'ID',
          render: ({ host_id }) => (
            <Anchor component={Link} size="sm" to={`/hosts/${host_id}`}>
              {host_id}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Host IDs"
              description="Show hosts with an ID that includes the specified number"
              placeholder="Search host IDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('host_id')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('host_id')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('host_id')] !== '',
        },
        {
          accessor: 'hostname',
          title: 'Hostname',
          render: ({ host_id, hostname }) => (
            <Anchor
              component={Link}
              size="sm"
              to={`/hosts/${host_id}`}
              className={`td-string-col ${classes.hostNameColumn}`}
            >
              {hostname}
            </Anchor>
          ),
          filter: (
            <FilterTextInput
              label="Hosts"
              description="Show hosts with the specified hostname"
              placeholder="Search hostnames..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('hostname')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('hostname')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('hostname')] !== '',
          width: '13%',
        },
        {
          accessor: 'host_description',
          title: 'Description',
          filter: (
            <FilterTextInput
              label="Description"
              description="Show hosts with the specified description"
              placeholder="Search descriptions..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('host_description')}
              defaultValue={
                queries[FILTER_ACCESSORS.indexOf('host_description')]
              }
            />
          ),
          filtering:
            queries[FILTER_ACCESSORS.indexOf('host_description')] !== '',
        },
        {
          accessor: 'sana_scid',
          title: 'SANA SCID',
          // sortable: true,
          filter: (
            <FilterTextInput
              label="SANA SCID"
              description="Show hosts with the SANA SCID that include the specified number"
              placeholder="Search SANA SCIDs..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('sana_scid')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('sana_scid')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('sana_scid')] !== '',
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
              description="Show hosts under operators with the specified name"
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
          width: '13%',
        },
        {
          accessor: 'word_size',
          title: 'Word Size',
          // sortable: true,
          filter: (
            <FilterTextInput
              label="Word size"
              description="Show hosts with a word size that include the specified number"
              placeholder="Search word sizes..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('word_size')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('word_size')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('word_size')] !== '',
        },
        {
          accessor: 'newline',
          title: 'Newline',
          // TODO: improve this with a TagsInput or PillsInput. E.g., if I only
          // want LF, it'll show both LF and CRLF at the moment.
          filter: (
            <FilterTextInput
              label="Newline"
              description="Show hosts using a newline that include the specified text"
              placeholder="Search newlines..."
              handleSetQuery={setQuery}
              queryIndex={FILTER_ACCESSORS.indexOf('newline')}
              defaultValue={queries[FILTER_ACCESSORS.indexOf('newline')]}
            />
          ),
          filtering: queries[FILTER_ACCESSORS.indexOf('newline')] !== '',
        },
      ]}
      idAccessor="host_id"
    />
  );

  return (
    <>
      <Group justify="space-between">
        <Text size="xl" fw={700}>
          Hosts
        </Text>
        {currentUser && (
          <NewButton component={Link} to={`/hosts/create`}>
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

export default HostTable;
