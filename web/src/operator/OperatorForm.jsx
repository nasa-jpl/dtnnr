import { Box, Button, Group, Space, TextInput, Title } from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatAllocator, formatGeneralError } from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

function OperatorForm({
  initialOperator,
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
      allocator_id: formatAllocator(initialOperator?.allocator)?.value ?? null,
      operator_name: initialOperator?.operator_name ?? '',
    },

    validate: {
      // In the case of PATCH, we could pass an empty JSON to not update
      // anything, but if we do pass the same values, things are fine, so
      // I'll just leave it as isNotEmpty.
      allocator_id: isNotEmpty('Allocator ID may not be empty.'),
      operator_name: isNotEmpty('Operator name should not be empty.'),
    },
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: (data, _variables, _context) => {
        if (method === 'POST') {
          navigate({ to: `/operators/${data.operator_id}` });
        } else if (method === 'PATCH') {
          closeModals();
        }
      },
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes(`Allocator ID ${values.allocator_id}`)) {
            // This can only happen if someone fetches /api/allocators and
            // before they submit the form, the allocator was deleted.
            form.setFieldValue('allocator_id', null);
            form.setFieldError(
              'allocator_id',
              `${error.detail}. Something was likely deleted.`,
            );
            scrollElementIntoView('allocator_id', false);
          } else {
            setErrorSection(
              `${error.detail}. Something was likely deleted, refresh the page.`,
            );
            scrollToErrorSection();
          }
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.includes(
              `to overlap with those of existing operators`,
            ): // fall through
            case error.detail.includes(`violates the unique constraint`):
              // Overlapping allocated node numbers / conflicting node numbers
              form.setFieldError('allocator_id', <span></span>);
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
      {formTitle && <Title order={3}>{formTitle}</Title>}
      {formDescription}
      <Space h="md" />
      <form
        onSubmit={form.onSubmit(
          (values) => handleSubmit(form, values),
          (errors) => {
            const firstErrorPath = Object.keys(errors)[0];
            scrollElementIntoView(
              form.getInputNode(firstErrorPath),
              firstErrorPath.includes('operator_name'),
            );
          },
        )}
      >
        <FetchSelect
          withAsterisk
          label="Allocator ID"
          placeholder="Allocator ID"
          queryKey={['allocators']}
          url={`/api/allocators`}
          initialValue={
            initialOperator
              ? initialOperator.allocator
              : { allocator_id: 0, allocator_name: 'Default Allocator' }
          }
          handleFormat={formatAllocator}
          {...form.getInputProps('allocator_id')}
          key={form.key('allocator_id')}
        />
        <TextInput
          withAsterisk
          label="Operator name"
          placeholder="Operator name"
          mt="sm"
          {...form.getInputProps('operator_name')}
          key={form.key('operator_name')}
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

export default OperatorForm;
