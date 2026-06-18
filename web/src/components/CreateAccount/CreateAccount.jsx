import {
  Anchor,
  Box,
  Button,
  Center,
  Container,
  Group,
  Paper,
  PasswordInput,
  rem,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { hasLength, useForm } from '@mantine/form';
import { IconArrowLeft } from '@tabler/icons-react';
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from '@tanstack/react-router';
import { useContext, useState } from 'react';
import AuthContext from '../../AuthContext';
import { formatGeneralError } from '../../utils/formatFunctions';
import { useRegisterMutation } from '../../utils/queries';
import { scrollElementIntoView, scrollToErrorSection } from '../../utils/util';
import { FormErrorSection } from '../FormErrorSection';
import classes from './CreateAccount.module.css';

export function CreateAccount() {
  const { currentUser } = useContext(AuthContext);
  const [errorSection, setErrorSection] = useState('');
  const mutation = useRegisterMutation();
  const navigate = useNavigate();
  const location = useLocation();
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      email: '',
      password: '',
    },

    validate: {
      // use same regex used by <input type="email"> https://html.spec.whatwg.org/multipage/input.html#e-mail-state-(type%3Demail)
      email: (val) =>
        /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/.test(
          val,
        )
          ? null
          : 'Invalid email address',
      password: hasLength(
        { min: 8, max: 128 },
        'Password must be within 8 and 128 characters, inclusive',
      ),
    },
  });

  async function handleSubmit(_form, values) {
    mutation.mutate(values, {
      onSuccess: (_data, _variables, _context) => {
        // If password is the proper length, Flask Security will always return
        // status code 200 for signing up even if no user was created as per
        // OWASP recommendations. Maybe have a notification here that, if possible,
        // a new user has been registered?
        navigate({ to: `/login${location.search}` }, { replace: true });
      },
      onError: (error, _variables, _context) => {
        setErrorSection(formatGeneralError(error));
        scrollToErrorSection();
      },
    });
  }

  return (
    <Container size={460} my={30}>
      {/* If already signed in, don't show this page */}
      {currentUser && <Navigate to="/" replace={true} />}
      <Title className={classes.title} ta="center">
        Create account
      </Title>
      <Text c="dimmed" fz="sm" ta="center">
        Enter a unique email and a password to register
      </Text>

      <form
        onSubmit={form.onSubmit(
          (values) => handleSubmit(form, values),
          (errors) => {
            const firstErrorPath = Object.keys(errors)[0];
            scrollElementIntoView(form.getInputNode(firstErrorPath));
          },
        )}
      >
        <Paper withBorder shadow="md" p={30} radius="md" mt="xl">
          <TextInput
            label="Email"
            placeholder="you@test.com"
            required
            {...form.getInputProps('email')}
            key={form.key('email')}
          />
          <PasswordInput
            label="Password"
            placeholder="New password"
            required
            mt="md"
            {...form.getInputProps('password')}
            key={form.key('password')}
          />
          <Group justify="space-between" mt="lg" className={classes.controls}>
            <Anchor
              c="dimmed"
              size="sm"
              className={classes.control}
              component={Link}
              to={`/login${location.search}`}
            >
              <Center inline>
                <IconArrowLeft
                  style={{ width: rem(12), height: rem(12) }}
                  stroke={1.5}
                />
                <Box ml={5}>Back to the login page</Box>
              </Center>
            </Anchor>
            <Button
              type="submit"
              className={classes.control}
              loading={mutation.isPending}
              onClick={() => setErrorSection('')}
            >
              Sign up
            </Button>
          </Group>
          {errorSection !== '' && (
            <FormErrorSection
              message={errorSection}
              setErrorSection={setErrorSection}
            />
          )}
        </Paper>
      </form>
    </Container>
  );
}
