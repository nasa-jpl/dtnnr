import { Anchor } from '@mantine/core';
import { Link } from '@tanstack/react-router';

export function LoginError({ error }) {
  return (
    <>
      {error.detail}.&nbsp;
      <Anchor component={Link} size="sm" to="/login" target="_blank">
        Log in
      </Anchor>
      &nbsp;again to refresh your credentials.
    </>
  );
}
