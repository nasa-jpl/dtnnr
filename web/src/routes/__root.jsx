import { AppShell } from '@mantine/core';
import { createRootRoute, Outlet, redirect } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools';
import ErrorComponent from '../components/ErrorComponent';
import { GlobalModal } from '../components/GlobalModal';
import Navbar from '../components/Navbar';

export const Route = createRootRoute({
  component: () => (
    <>
      <GlobalModal />
      <AppShell header={{ height: 59.2 }} padding="md">
        <AppShell.Header>
          <Navbar />
        </AppShell.Header>
        <AppShell.Main className="app-shell-main">
          <Outlet />
        </AppShell.Main>
      </AppShell>
      <TanStackRouterDevtools />
    </>
  ),
  errorComponent: ({ error }) => <ErrorComponent error={error} />,
  beforeLoad: ({ location }) => {
    if (location.pathname === '/') {
      throw redirect({ to: '/nodes' });
    }
  },
});
