import { QueryClient } from '@tanstack/react-query';
import { createRouter, RouterProvider, redirect } from '@tanstack/react-router';
import { useContext } from 'react';
import AuthContext, { fetchWhoami } from './AuthContext';
import ErrorComponent from './components/ErrorComponent';
import { routeTree } from './routeTree.gen';

export const queryClient = new QueryClient();

export async function authBeforeLoad({ location, context: { currentUser } }) {
  // TODO: visiting a protected page for the first time does not have AuthContext
  // updated so currentUser isn't set. Idk how to fix this, so we call
  // fetchWhomai() as a workaround.
  let cuser = currentUser ?? (await fetchWhoami());
  if (!cuser) {
    throw redirect({
      to: '/login',
      search: {
        from: location.pathname,
      },
    });
  }
  return null;
}

const router = createRouter({
  routeTree,
  context: { queryClient, currentUser: undefined },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
  errorComponent: ({ error }) => <ErrorComponent error={error} />,
  defaultNotFoundComponent: () => <ErrorComponent />,
});

export function App() {
  const { currentUser } = useContext(AuthContext);
  return <RouterProvider router={router} context={{ currentUser }} />;
}
