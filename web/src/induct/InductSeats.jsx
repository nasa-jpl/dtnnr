import { Button, Loader, Text } from '@mantine/core';
import { Fragment } from 'react';
import { formatSeat } from '../utils/formatFunctions';
import { useInductSeatQuery } from '../utils/queries';

export function InductSeats({ inductId }) {
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
  } = useInductSeatQuery(inductId);

  return status === 'pending' ? (
    <Loader type="dots" />
  ) : status === 'error' ? (
    <Text>Error: {error.message}</Text>
  ) : (
    <div>
      {data.pages
        .flatMap((p) => p.items)
        .map((s) => (
          <Fragment key={s.seat_id}>
            <Text>{formatSeat(s).label}</Text>
          </Fragment>
        ))}
      <Button
        onClick={() => fetchNextPage()}
        disabled={!hasNextPage || isFetching}
        type="button"
        size="compact-sm"
        mt="xs"
      >
        {isFetchingNextPage
          ? 'Loading more...'
          : hasNextPage
            ? 'Load More'
            : 'Nothing more to load'}
      </Button>
    </div>
  );
}
