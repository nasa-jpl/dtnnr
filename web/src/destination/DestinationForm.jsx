import {
  Box,
  Button,
  Checkbox,
  Group,
  Space,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError } from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

function DestinationForm({
  initialDestination,
  hostId,
  closeModals,
  mutation,
  notFoundErrorMessage,
  formDescription,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();

  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      destination_value: undefined,
      ip: undefined,
    },

    initialDirty: {
      destination_value: true,
      ip: true,
    },

    validateInputOnChange: true,
    validate: {
      destination_value: (value, values) => {
        const ipRegex =
          /(^((?=.*::)(?!.*::.+::)(::)?([\dA-F]{1,4}:(:|\b)|){5}|([\dA-F]{1,4}:){6})((([\dA-F]{1,4}((?!\3)::|:\b|$))|(?!\2\3)){2}|(((2[0-4]|1\d|[1-9])?\d|25[0-5])\.?\b){4})$)|(^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$)/i;
        if (values.ip && !ipRegex.test(value)) {
          return 'Invalid IPv4 or IPv6 address';
        }
      },
    },
  });

  if (!initializedFormValues.current) {
    form.setValues({
      destination_value: initialDestination?.destination_value ?? '',
      ip: false,
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    let { ip, ...body } = values;
    let mutationValues = {
      body,
      searchParams: new URLSearchParams({ ip }),
    };
    mutation.mutate(mutationValues, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Host ID')) {
            // For creating: when someone is still on the host's details page
            // and someone deleted the host.
            queryClient.invalidateQueries({ queryKey: ['hosts', hostId] });
          } else if (error.detail.includes('Destination ID')) {
            // For editing: when someone has this form open but the destination
            // was deleted.
            queryClient.invalidateQueries({
              queryKey: ['hosts', hostId, 'destinations'],
            });
          }
          setErrorSection(notFoundErrorMessage);
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.includes(`already associated`):
              form.setFieldError('destination_value', error.detail);
              scrollElementIntoView(form.getInputNode('destination_value'));
              break;
            default:
              // Unexpected backend error
              setErrorSection(formatGeneralError(error));
              scrollToErrorSection();
          }
        } else if (error.status === 401 && error.detail) {
          setErrorSection(<LoginError error={error} />);
          scrollToErrorSection();
        } else {
          setErrorSection(formatGeneralError(error));
          scrollToErrorSection();
        }
      },
    });
  }

  return (
    <Box maw={500} mx="auto">
      <Text c="dimmed" size="sm">
        {formDescription}
      </Text>
      <Space h="md" />
      <form
        onSubmit={form.onSubmit(
          (values) => handleSubmit(form, values),
          (errors) => {
            const firstErrorPath = Object.keys(errors)[0];
            scrollElementIntoView(form.getInputNode(firstErrorPath));
          },
        )}
      >
        <TextInput
          label="Destination"
          placeholder="Destination"
          data-autofocus
          {...form.getInputProps('destination_value')}
          key={form.key('destination_value')}
        />
        <Checkbox
          label="Validate as an IP address"
          mt="sm"
          {...form.getInputProps('ip')}
          key={form.key('ip')}
        />
        <Group justify="flex-end" mt="md">
          <Button
            type="submit"
            loading={mutation.isPending}
            onClick={() => setErrorSection('')}
          >
            Submit
          </Button>
        </Group>
        {errorSection !== '' && (
          <FormErrorSection
            message={errorSection}
            setErrorSection={setErrorSection}
          />
        )}
      </form>
    </Box>
  );
}

export default DestinationForm;
