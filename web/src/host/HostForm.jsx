import {
  Box,
  Button,
  Group,
  NumberInput,
  Select,
  Space,
  TextInput,
  Title,
} from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useRef, useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError, formatOperator } from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';
import { isInIntRange } from '../utils/validateFunctions';

function HostForm({
  initialHost,
  closeModals,
  mutation,
  formTitle,
  formDescription,
  method,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const navigate = useNavigate();
  const form = useForm({
    mode: 'uncontrolled',

    // Mantine form re-renders when dirty field status changes. Force it to
    // always be dirty. No input can change a field back to `undefined`.
    initialValues: {
      hostname: undefined,
      host_description: undefined,
      operator_id: undefined,
      sana_scid: undefined,
      word_size: undefined,
      newline: undefined,
    },

    initialDirty: {
      hostname: true,
      host_description: true,
      operator_id: true,
      sana_scid: true,
      word_size: true,
      newline: true,
    },

    transformValues: (values) => ({
      ...values,
      host_description: values.host_description
        ? values.host_description
        : null,
      sana_scid: values.sana_scid !== '' ? values.sana_scid : null,
    }),

    validate: {
      hostname: isNotEmpty('Hostname may not be empty.'),
      sana_scid: isInIntRange(),
    },
  });

  if (initialHost && !initializedFormValues.current) {
    form.setValues({
      hostname: initialHost.hostname,
      host_description: initialHost.host_description,
      operator_id: formatOperator(initialHost.operator)?.value ?? null,
      sana_scid: initialHost.sana_scid,
      word_size:
        initialHost.word_size !== null ? String(initialHost.word_size) : null,
      newline: initialHost.newline,
    });
    initializedFormValues.current = true;
  } else if (!initializedFormValues.current) {
    form.setValues({
      hostname: '',
      host_description: null,
      operator_id: null,
      sana_scid: null,
      word_size: null,
      newline: null,
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: (data, _variables, _context) => {
        if (method === 'POST') {
          navigate({ to: `/hosts/${data.host_id}` });
        } else if (method === 'PATCH') {
          closeModals();
        }
      },
      onError: (error) => {
        if (error.status === 404) {
          if (
            error.detail.includes(
              `Operator ID ${values.operator_id} does not exist`,
            )
          ) {
            // This can only happen if someone fetches /api/operators and
            // before they submit the form, the operator was deleted.
            form.setFieldValue('operator_id', null);
            form.setFieldError(
              'operator_id',
              `${error.detail}. Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('operator_id'), false);
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
              `likely need to update these nodes to have a null operator_id`,
            ):
              form.setFieldError('operator_id', <span></span>);
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
              !firstErrorPath.includes('operator_id'),
            );
          },
        )}
      >
        <TextInput
          withAsterisk
          label="Hostname"
          placeholder="Hostname"
          {...form.getInputProps('hostname')}
          key={form.key('hostname')}
        />
        <TextInput
          label="Host description"
          placeholder="Host description"
          mt="sm"
          {...form.getInputProps('host_description')}
          key={form.key('host_description')}
        />
        <FetchSelect
          label="Operator"
          placeholder="Operator"
          queryKey={['operators']}
          url={`/api/operators`}
          initialValue={initialHost?.operator}
          handleFormat={formatOperator}
          mt="sm"
          {...form.getInputProps('operator_id')}
          key={form.key('operator_id')}
        />
        <NumberInput
          label="SANA SCID"
          placeholder="SANA SCID"
          allowNegative={false}
          allowDecimal={false}
          mt="sm"
          {...form.getInputProps('sana_scid')}
          key={form.key('sana_scid')}
        />
        <Select
          label="Word size (bit)"
          placeholder="Word size (bit)"
          data={['32', '64']}
          mt="sm"
          {...form.getInputProps('word_size')}
          key={form.key('word_size')}
        />
        <Select
          label="Newline"
          placeholder="Newline"
          data={[
            'U+000A LINE FEED (LF)',
            'U+000B LINE TABULATION (VT)',
            'U+000C FORM FEED (FF)',
            'U+000D CARRIAGE RETURN (CR)',
            'U+000D + U+000A (CRLF)',
            'U+0085 NEXT LINE (NEL)',
            'U+2028 LINE SEPARATOR',
            'U+2029 PARAGRAPH SEPARATOR',
          ]}
          mt="sm"
          {...form.getInputProps('newline')}
          key={form.key('newline')}
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

export default HostForm;
