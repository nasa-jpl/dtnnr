import {
  Box,
  Button,
  Group,
  NumberInput,
  Radio,
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
import { isInBigIntRange } from '../utils/validateFunctions';

export function EndpointIpnForm({
  initialEndpoint,
  nodeId,
  closeModals,
  mutation,
  formDescription,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();

  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      service_number: undefined,
      disposition: undefined,
      application: undefined,
    },

    transformValues: (values) => ({
      ...values,
      application: values.application ? values.application : null,
    }),

    validate: {
      service_number: (value) =>
        value === ''
          ? `Service number may not be empty.`
          : isInBigIntRange()(value),
      disposition: (value) =>
        value !== 'x' && value !== 'q'
          ? `Disposition must be 'x' or 'q'.`
          : null,
    },
  });

  if (!initializedFormValues.current) {
    form.setValues({
      service_number: initialEndpoint?.service_number ?? '',
      disposition: initialEndpoint?.disposition ?? 'x',
      application: initialEndpoint?.application ?? '',
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Node ID')) {
            // For creating/editing: when someone is on the node's details page
            // and someone deleted the node.
            queryClient.invalidateQueries({ queryKey: ['nodes', nodeId] });
            setErrorSection(
              `${error.detail}. Node was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('EID')) {
            // For editing: either node or the endpoint was deleted while editing.
            queryClient.invalidateQueries({
              queryKey: ['nodes', nodeId, 'endpoints'],
            });
            setErrorSection(
              `${error.detail}. Endpoint was deleted, refresh the table.`,
            );
          } else {
            setErrorSection(
              `${error.detail}. Something was likely deleted, refresh the page or table.`,
            );
          }
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.includes(`already exists`):
              form.setFieldError('service_number', error.detail);
              scrollElementIntoView(form.getInputNode('service_number'));
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
        <NumberInput
          label="Service number"
          placeholder="Service number"
          allowNegative={false}
          allowDecimal={false}
          withAsterisk
          {...form.getInputProps('service_number')}
          key={form.key('service_number')}
        />
        <Radio.Group
          name="disposition"
          label="Disposition"
          /* TODO: provide a description here from `man bprc`? */
          withAsterisk
          mt="sm"
          {...form.getInputProps('disposition')}
          key={form.key('disposition')}
        >
          <Group>
            {/* TODO: rename these to "Execute" and "Queue" ? */}
            <Radio value="x" label="x" />
            <Radio value="q" label="q" />
          </Group>
        </Radio.Group>
        <TextInput
          label="Application"
          placeholder="Application"
          mt="sm"
          {...form.getInputProps('application')}
          key={form.key('application')}
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
