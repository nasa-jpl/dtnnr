import { Box, Button, Group, Space, Text, TextInput } from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

export function ContactForm({
  initialContact,
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
      contact_name: initialContact?.contact_name ?? '',
      email: initialContact?.email ?? '',
    },

    transformValues: (values) => ({
      ...values,
      email: values.email !== '' ? values.email : null,
    }),

    validate: {
      contact_name: isNotEmpty('Name may not be blank.'),
    },
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          // Messages for allocator/operator/host/node only appear for
          // creating (POST)
          if (error.detail.includes('Allocator ID')) {
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
          } else if (error.detail.includes('Contact id')) {
            // This message only appears for updating (PATCH)
            queryClient.invalidateQueries({
              queryKey: ['contacts', initialContact.contact_id],
            });
            setErrorSection(
              `${error.detail}. Point of contact was deleted, refresh the page.`,
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
            // Shouldn't happen if frontend validation works
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.title.includes('Bad Request'):
              setErrorSection(error.detail);
              scrollToErrorSection();
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
    <Box maw={600} mx="auto">
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
          withAsterisk
          label="Contact name"
          placeholder="Contact name"
          {...form.getInputProps('contact_name')}
          key={form.key('contact_name')}
        />
        <TextInput
          type="email"
          label="Email"
          placeholder="some_email@test.com"
          {...form.getInputProps('email')}
          key={form.key('email')}
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
