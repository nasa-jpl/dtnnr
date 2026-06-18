import {
  ActionIcon,
  Anchor,
  Button,
  Group,
  Switch,
  Title,
  Tooltip,
  useMantineColorScheme,
  useMantineTheme,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconLogin,
  IconLogout,
  IconMoonStars,
  IconSun,
} from '@tabler/icons-react';
import { Link, useLocation, useNavigate } from '@tanstack/react-router';
import { useContext } from 'react';
import AuthContext from '../AuthContext';
import { formatGeneralError } from '../utils/formatFunctions';
import { useLogoutMutation } from '../utils/queries';

// TODO: Consider renaming this to Header or something since it doesn't
// really perform any navigation besides home page and login screen, and
// it can be confusing with AppShell.Navbar having a different meaning
function Navbar() {
  const { currentUser, checkWhoami } = useContext(AuthContext);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const theme = useMantineTheme();
  const mutation = useLogoutMutation();
  const location = useLocation();
  const navigate = useNavigate();

  const sunIcon = (
    <IconSun
      className="icon-16-px"
      stroke={2.5}
      color={theme.colors.yellow[4]}
    />
  );

  const moonIcon = (
    <IconMoonStars
      className="icon-16-px"
      stroke={2.5}
      color={theme.colors.blue[6]}
    />
  );

  const loginIcon = <IconLogin className="icon-16-px" stroke={2.5} />;

  const logoutIcon = <IconLogout className="icon-16-px" stroke={2.5} />;

  async function handleLogout() {
    mutation.mutate(
      {},
      {
        onSuccess: (_data, _variables, _context) => {
          checkWhoami();
          // When someone logs out from the create form pages, they probably
          // intend to not see that page anymore
          if (location.pathname.includes('create')) {
            navigate({
              to: location.pathname.slice(
                0,
                location.pathname.indexOf('/create'),
              ),
            });
          }
        },
        onError: (error, _variables, _context) =>
          notifications.show({
            title: 'Failed to log out',
            message: formatGeneralError(error),
            withCloseButton: true,
            color: 'red',
          }),
      },
    );
  }

  function getLoginString() {
    // We don't want to redirect back to /login after logging in
    if (location.pathname.includes('login')) {
      return '/login';
    }
    let params = new URLSearchParams();
    params.set('from', location.pathname);
    return `/login?${params.toString()}`;
  }

  /* TODO: re-enable login/logout buttons after API supports it */

  const rightSection = (
    <Group visibleFrom="xs">
      <Switch
        checked={colorScheme === 'dark'}
        onChange={toggleColorScheme}
        size="md"
        color="dark.4"
        onLabel={sunIcon}
        offLabel={moonIcon}
        aria-label="Toggle color scheme"
      />
      {/* { currentUser ?
        <Button
          leftSection={logoutIcon}
          variant="outline"
          loading={mutation.isPending}
          onClick={() => handleLogout()}
        >
          Log out
        </Button>
        :
        <Button
          leftSection={loginIcon}
          variant="outline"
          component={Link}
          to={getLoginString()}
        >
          Log in
        </Button>
      } */}
    </Group>
  );

  const smallRightSection = (
    <Group hiddenFrom="xs" gap="sm">
      <Tooltip label={`${colorScheme === 'dark' ? 'Light' : 'Dark'} mode`}>
        <ActionIcon
          onClick={toggleColorScheme}
          variant="default"
          size="lg"
          aria-label="Toggle color scheme"
        >
          {colorScheme === 'dark' ? sunIcon : moonIcon}
        </ActionIcon>
      </Tooltip>
      {/* <Tooltip label={currentUser ? 'Log out' : 'Log in'}>
        {currentUser ?
          <ActionIcon
            variant="outline"
            size="lg"
            loading={mutation.isPending}
            onClick={() => handleLogout()}
          >
            {logoutIcon}
          </ActionIcon>
          :
          <ActionIcon
            variant="outline"
            size="lg"
            component={Link}
            to={getLoginString()}
          >
            {loginIcon}
          </ActionIcon>
        }
      </Tooltip> */}
    </Group>
  );

  // TODO: When viewport is small, we use ActionIcons for the light/dark
  // mode and login/logout buttons.
  // If we ever want to put more stuff in this component, I don't think
  // there'll be enough space, and we should move everything into an
  // AppShell.Navbar and replace this right section with a Burger.
  return (
    <Group h="100%" px="md" justify="space-between">
      <Anchor
        component={Link}
        to="/"
        underline="never"
        c={colorScheme === 'dark' ? theme.white : theme.black}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'left',
        }}
      >
        <Title order={4}>DTN Node Registry</Title>
      </Anchor>
      {rightSection}
      {smallRightSection}
    </Group>
  );
}

export default Navbar;
