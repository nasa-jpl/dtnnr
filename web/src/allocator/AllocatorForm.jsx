import {
  Box,
  Button,
  Group,
  NumberInput,
  Space,
  TextInput,
  Title,
} from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError } from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

function AllocatorForm({
  initialAllocator,
  closeModals,
  mutation,
  formTitle,
  formDescription,
  method,
}) {
  const [errorSection, setErrorSection] = useState('');
  const navigate = useNavigate();
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      allocator_id: initialAllocator?.allocator_id ?? '',
      allocator_name: initialAllocator?.allocator_name ?? '',
    },

    validate: {
      allocator_id: (value) =>
        value === ''
          ? 'Allocator ID may not be null.'
          : BigInt(value) < 0 || BigInt(value) > 9223372036854775807n
            ? 'Allocator ID must be between 0 and 2^63 - 1.'
            : null,
      allocator_name: isNotEmpty('Allocator name should not be empty.'),
    },
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: (data, _variables, _context) => {
        if (method === 'POST') {
          navigate({ to: `/allocators/${data.allocator_id}` });
        } else if (method === 'PATCH') {
          if (data.allocator_id !== initialAllocator.allocator_id) {
            navigate({ to: `/allocators/${data.allocator_id}` });
          }
          closeModals();
        }
      },
      onError: (error) => {
        if (error.status === 404) {
          // Should never happen when creating.
          // For updating: the allocator was deleted while editing
          setErrorSection(
            `${error.detail}. Something was likely deleted, refresh the page.`,
          );
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.includes(`already exists`):
              form.setFieldError('allocator_id', error.detail);
              scrollElementIntoView(form.getInputNode('allocator_id'));
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
      {formTitle && <Title order={3}>{formTitle}</Title>}
      {formDescription}
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
          withAsterisk
          label="Allocator ID"
          placeholder="Allocator ID"
          allowNegative={false}
          allowDecimal={false}
          {...form.getInputProps('allocator_id')}
          key={form.key('allocator_id')}
        />
        <TextInput
          withAsterisk
          label="Allocator name"
          placeholder="Allocator name"
          mt="sm"
          {...form.getInputProps('allocator_name')}
          key={form.key('allocator_name')}
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

export default AllocatorForm;
