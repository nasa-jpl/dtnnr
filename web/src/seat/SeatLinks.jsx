import { Button, Loader, Text } from '@mantine/core';
import { Fragment } from 'react';
import { formatLinkForTable } from '../utils/formatFunctions';
import { useSeatLinkQuery } from '../utils/queries';

export function SeatLinks({ seatId }) {
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
  } = useSeatLinkQuery(seatId);

  return status === 'pending' ? (
    <Loader type="dots" />
  ) : status === 'error' ? (
    <Text>Error: {error.message}</Text>
  ) : (
    <div>
      {data.pages
        .flatMap((p) => p.items)
        .map((l) => (
          <Fragment key={l.link_id}>
            <Text>{formatLinkForTable(l)}</Text>
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
            ? 'Load more'
            : 'Nothing more to load'}
      </Button>
    </div>
  );
}
