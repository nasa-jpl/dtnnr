import { ActionIcon, Loader, rem, Select, Text } from '@mantine/core';
import { IconCheck, IconRefresh } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { formatGeneralError } from '../utils/formatFunctions';
import { getAllQuery } from '../utils/queries';
import classes from './FetchSelect.module.css';

export function FetchSelectOption({ option, checked, renderValue }) {
  const iconProps = {
    color: 'currentColor',
    opacity: 0.6,
  };
  return (
    <div className={classes.optionContainer}>
      {checked && (
        <IconCheck
          className={`${classes.optionIcon} icon-18-px`}
          {...iconProps}
        />
      )}
      {renderValue && (
        <Text className={classes.optionValue}>{option.value}</Text>
      )}
      <Text className={`${classes.optionLabel} show-white-space`}>
        {renderValue
          ? option.label.substring(option.label.indexOf(' ') + 1)
          : option.label}
      </Text>
    </div>
  );
}

export const optionsFilter = ({ options, search, limit }) => {
  const query = search.toLowerCase().trim();
  if (!query) {
    return options.slice(0, limit);
  }
  const splittedSearch = query.split(' ');
  const result = [];

  for (let i = 0; i < options.length; i++) {
    if (result.length >= limit) {
      break;
    }
    const option = options[i];
    if (
      splittedSearch.every((searchWord) =>
        option._searchString.includes(searchWord),
      )
    ) {
      result.push(option);
    }
  }

  return result;
};

export function prepareFormattedData(items, handleFormat) {
  if (!items) {
    return [];
  }
  return items.map((item) => {
    const formatted = handleFormat(item);
    return {
      ...formatted,
      _searchString: formatted.label.toLowerCase().trim(),
    };
  });
}

function FetchSelect({
  queryKey,
  url,
  initialValue,
  handleFormat,
  renderValue = true,
  ...otherProps
}) {
  const queryClient = useQueryClient();
  const { isPending, isError, isFetching, data, error } = useQuery(
    getAllQuery(queryKey, url),
  );
  const formattedData = useMemo(
    () => prepareFormattedData(data?.items, handleFormat),
    [data, handleFormat],
  );

  if (isPending) {
    return (
      <Select
        {...otherProps}
        // Mantine's uncontrolled forms means components won't re-render when
        // form data changes.
        // When our query is first called, the cache is empty so we have an empty
        // array. Using a controlled form, after the cache is filled, the component
        // would re-render and the currently selected option will be rendered.
        // But using an uncontrolled form, if we already had a value selected, it
        // will not show because the component will not have re-rendered because
        // form data has not changed.
        // In cases where we already have a value selected, we know what the value
        // is before using this FetchSelect component, so we can pass in that initial
        // value, so that the value will be rendered even when the cache is empty.
        data={initialValue ? [initialValue].map(handleFormat) : []}
        disabled
        rightSection={<Loader size={rem(20)} />}
      />
    );
  }

  if (isError) {
    return (
      <Select
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
    <Select
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

export default FetchSelect;
