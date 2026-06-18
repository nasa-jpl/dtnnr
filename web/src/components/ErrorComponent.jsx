import { Anchor, Space, Text, Title } from '@mantine/core';
import { Link } from '@tanstack/react-router';
import { Route as nodesRoute } from '../routes/_home.nodes';
import { formatGeneralError } from '../utils/formatFunctions';

function ErrorComponent({ error }) {
  return (
    <>
      <Title order={2}>
        {error?.status ? error.status : error ? 'Error' : 'Page not found'}
      </Title>
      <Space h="lg" />
      <Text>
        {formatGeneralError(
          error,
          // TODO: link to our GitHub issues page?
          'Nothing found. If this is unexpected, please let us know by opening\
           an issue.',
        )}
      </Text>
      <Space h="md" />
      <Anchor component={Link} to={nodesRoute.to}>
        Go back to the home page
      </Anchor>
    </>
  );
}

export default ErrorComponent;
