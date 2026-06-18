import { ActionIcon, Loader, MultiSelect, rem } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { formatGeneralError } from '../utils/formatFunctions';
import { getAllQuery } from '../utils/queries';
import {
  FetchSelectOption,
  optionsFilter,
  prepareFormattedData,
} from './FetchSelect';

export function FetchMultiSelect({
  queryKey,
  url,
  initialValue,
  handleFormat,
  renderValue = true,
  processData = (data) => data?.items ?? [],
  ...otherProps
}) {
  const queryClient = useQueryClient();
  const { isPending, isError, isFetching, data, error } = useQuery(
    getAllQuery(queryKey, url),
  );
  const formattedData = useMemo(
    () => prepareFormattedData(processData(data), handleFormat),
    [data, handleFormat, processData],
  );

  if (isPending) {
    return (
      <MultiSelect
        {...otherProps}
        data={initialValue ? initialValue.map(handleFormat) : []}
        disabled
        rightSection={<Loader size={rem(20)} />}
      />
    );
  }

  if (isError) {
    return (
      <MultiSelect
        data={[]}
        searchable
        nothingFoundMessage={formatGeneralError(error)}
        rightSectionPointerEvents="auto"
        rightSection={
          <ActionIcon
            loading={isFetching}
            onClick={() => queryClient.invalidateQueries({ queryKey })}
          >
            <IconRefresh className="icon-20-px" />
          </ActionIcon>
        }
        {...otherProps}
      />
    );
  }

  return (
    <MultiSelect
      styles={{ pill: { whiteSpace: 'pre' } }}
      data={formattedData}
      limit={20}
      searchable
      nothingFoundMessage="No records found"
      renderOption={FetchSelectOption}
      filter={optionsFilter}
      clearable
      {...otherProps}
    />
  );
}
