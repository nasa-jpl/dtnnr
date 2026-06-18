import { Box, Button, Group, Space, Text } from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatContact, formatGeneralError } from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

export function ExistingContactForm({
  allocatorId,
  operatorId,
  hostId,
  nodeId,
  closeModals,
  mutation,
  formDescription,
}) {
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();

  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      existing_contact_id: null,
    },

    validate: {
      existing_contact_id: isNotEmpty('Contact ID may not be null.'),
    },
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Contact ID')) {
            // Contact list is outdated
            queryClient.invalidateQueries({
              queryKey: ['contacts'],
              exact: true,
            });
          } else if (error.detail.includes('Allocator ID')) {
            // Allocator was deleted
            queryClient.invalidateQueries({
              queryKey: ['allocators', allocatorId],
            });
            setErrorSection(
              `${error.detail}. Allocator was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('Operator ID')) {
            // Operator was deleted
            queryClient.invalidateQueries({
              queryKey: ['operators', operatorId],
            });
            setErrorSection(
              `${error.detail}. Operator was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('Host ID')) {
            // Host was deleted
            queryClient.invalidateQueries({ queryKey: ['hosts', hostId] });
            setErrorSection(
              `${error.detail}. Host was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('Node ID')) {
            // Node was deleted
            queryClient.invalidateQueries({ queryKey: ['nodes', nodeId] });
            setErrorSection(
              `${error.detail}. Node was deleted, refresh the page.`,
            );
          } else {
            // Don't know when this could ever happen
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
            case error.detail.includes('Contact ID'):
              form.setFieldError('existing_contact_id', error.detail);
              scrollElementIntoView(
                form.getInputNode('existing_contact_id'),
                false,
              );
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
            scrollElementIntoView(form.getInputNode(firstErrorPath), false);
          },
        )}
      >
        <FetchSelect
          label="Point of contact"
          placeholder="Point of contact"
          queryKey={['contacts']}
          url={`/api/contacts`}
          handleFormat={formatContact}
          {...form.getInputProps('existing_contact_id')}
          key={form.key('existing_contact_id')}
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
