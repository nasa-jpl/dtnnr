// Taken from https://ui.mantine.dev/category/authentication/#authentication-title
import {
  Anchor,
  Button,
  Checkbox,
  Container,
  Group,
  Paper,
  PasswordInput,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { hasLength, useForm } from '@mantine/form';
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from '@tanstack/react-router';
import { useContext, useState } from 'react';
import AuthContext from '../../AuthContext';
import { formatGeneralError } from '../../utils/formatFunctions';
import { useLogInMutation } from '../../utils/queries';
import { scrollElementIntoView, scrollToErrorSection } from '../../utils/util';
import { FormErrorSection } from '../FormErrorSection';
import classes from './AuthenticationTitle.module.css';

export function AuthenticationTitle() {
  const { currentUser, checkWhoami } = useContext(AuthContext);
  const [errorSection, setErrorSection] = useState('');
  const mutation = useLogInMutation();
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const from = params.get('from') || '/';
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      email: '',
      password: '',
      remember: false,
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

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: (_data, _variables, _context) => {
        checkWhoami();
        navigate({ to: from }, { replace: true });
      },
      onError: (error, _variables, _context) => {
        if (
          error?.detail?.includes(`Authentication failed`) &&
          error?.detail?.includes(`invalid`)
        ) {
          form.setFieldError('email', <span></span>);
          form.setFieldError('password', <span></span>);
        }
        setErrorSection(formatGeneralError(error));
        scrollToErrorSection();
      },
    });
  }

  function getSignupString() {
    // Let the /signup endpoint know the ?from for this /login
    if (from === '/') {
      return `/signup`;
    }
    return `/signup${location.search}`;
  }

  return (
    <Container size={420} my={40}>
      {/* If already signed in, don't show this page */}
      {currentUser && <Navigate to="/" replace={true} />}
      <Title ta="center" className={classes.title}>
        Welcome back!
      </Title>
      <Text c="dimmed" size="sm" ta="center" mt={5}>
        Do not have an account yet?{' '}
        <Anchor size="sm" component={Link} to={getSignupString()}>
          Create account
        </Anchor>
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
        <Paper withBorder shadow="md" p={30} mt={30} radius="md">
          <TextInput
            label="Email"
            placeholder="you@test.com"
            required
            {...form.getInputProps('email')}
            key={form.key('email')}
          />
          <PasswordInput
            label="Password"
            placeholder="Your password"
            required
            mt="md"
            {...form.getInputProps('password')}
            key={form.key('password')}
          />
          <Group justify="space-between" mt="lg">
            <Checkbox
              label="Remember me"
              {...form.getInputProps('remember', { type: 'checkbox' })}
            />
            {/* <Anchor component="button" size="sm">
              Forgot password?
            </Anchor> */}
          </Group>
          <Button
            type="submit"
            fullWidth
            mt="xl"
            loading={mutation.isPending}
            onClick={() => setErrorSection('')}
          >
            Sign in
          </Button>
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
