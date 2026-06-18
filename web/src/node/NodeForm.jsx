import {
  Box,
  Button,
  Checkbox,
  Fieldset,
  Group,
  NumberInput,
  Space,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useRef, useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import {
  formatAllocator,
  formatGeneralError,
  formatHost,
  formatOperator,
} from '../utils/formatFunctions';
import {
  drill,
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';
import { isInBigIntRangePositive } from '../utils/validateFunctions';
import { DestinationRefModeRadio } from './DestinationRefModeRadio';

const destination_ref_mode_options = [
  {
    name: 'nullify',
    description: `Inducts and seats drop their references to destinations.`,
  },
  {
    name: 'associate',
    description: `Inducts and seats update their destination references to an
      equivalent destination under the new host. References without an
      equivalent destination are dropped`,
  },
  {
    name: 'copy',
    description: `Inducts and seats update their destination references to an
      equivalent destination under the new host. References without an
      equivalent destination are copied to the new host.`,
  },
];

function NodeForm({
  initialNode,
  closeModals,
  mutation,
  formTitle,
  formDescription,
  method,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const [showDestRefMode, setShowDestRefMode] = useState(false);
  const [destRefModeRadioDisabled, setDestRefModeRadioDisabled] = useState(
    initialNode?.host,
  );
  const navigate = useNavigate();
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      allocator_id: undefined,
      node_number: undefined,
      host_id: undefined,
      operator_id: undefined,
      sdr_wm_size: undefined,
      sdr_config_flags: undefined,
      heap_words: undefined,
      wm_size: undefined,
      node_name: undefined,
      comments: undefined,
      destination_ref_mode: undefined,
    },

    initialDirty: {
      allocator_id: true,
      node_number: true,
      host_id: true,
      operator_id: true,
      sdr_wm_size: true,
      sdr_config_flags: true,
      heap_words: true,
      wm_size: true,
      node_name: true,
      comments: true,
      destination_ref_mode: true,
    },

    // TODO: do we need this??
    enhanceGetInputProps: ({ _inputProps, field, options, form }) => {
      if (options.type === 'ToggleTextFetchSelect') {
        return {
          // A field that will be copied is `undefined`
          editing: drill(form.getValues(), field) !== undefined,
          canEdit: form.getValues().destination_ref_mode,
          setFieldValue: (v) => form.setFieldValue(field, v),
        };
      }
    },

    validate: {
      allocator_id: (value, values) =>
        value === null && values.operator_id === null
          ? 'Allocator ID may not be empty.'
          : null,
      node_number: (value) =>
        value === ''
          ? `Node number may not be empty.`
          : Number(value) < 0 || Number(value) > 2 ** 32 - 1
            ? `Node number must be between 0 and ${2 ** 32 - 1}`
            : null,
      sdr_wm_size: isInBigIntRangePositive(),
      heap_words: isInBigIntRangePositive(),
      wm_size: isInBigIntRangePositive(),
    },

    transformValues: (values) => {
      let res = {
        // Deep copy since we have arrays of objects
        ...JSON.parse(JSON.stringify(values)),
        sdr_wm_size: values.sdr_wm_size !== '' ? values.sdr_wm_size : null,
        sdr_config_flags:
          values.sdr_config_flags.length !== 0 ? values.sdr_config_flags : null,
        heap_words: values.heap_words !== '' ? values.heap_words : null,
        wm_size: values.wm_size !== '' ? values.wm_size : null,
        node_name: values.node_name ? values.node_name : null,
        comments: values.comments ? values.comments : null,
      };
      if (res.operator_id !== null) {
        delete res.allocator_id;
      }
      if (
        method !== 'PATCH' ||
        values.host_id === `${initialNode?.host?.host_id}`
      ) {
        delete res.destination_ref_mode;
      }
      return res;
    },
  });
  form.watch('host_id', ({ value, _dirty }) => {
    if (method === 'PATCH' && (initialNode.host?.host_id ?? null) !== value) {
      if (value === null) {
        // Having a host -> hostless should always be nullify
        form.setFieldValue('destination_ref_mode', 'nullify');
        setDestRefModeRadioDisabled(true);
      } else {
        // If value changed, then disable radio buttons only if initial node
        // was hostless.
        setDestRefModeRadioDisabled(initialNode.host === null);
      }
      setShowDestRefMode(true);
    } else {
      form.setFieldValue('destination_ref_mode', 'nullify');
      setShowDestRefMode(false);
    }
  });

  if (!initializedFormValues.current) {
    form.setValues({
      allocator_id: formatAllocator(initialNode?.allocator)?.value ?? null,
      node_number: initialNode?.node_number ?? '',
      host_id: formatHost(initialNode?.host)?.value ?? null,
      operator_id: formatOperator(initialNode?.operator)?.value ?? null,
      sdr_wm_size: initialNode?.sdr_wm_size ?? '',
      sdr_config_flags: initialNode?.sdr_config_flags ?? [],
      heap_words: initialNode?.heap_words ?? '',
      wm_size: initialNode?.wm_size ?? '',
      node_name: initialNode?.node_name ?? '',
      comments: initialNode?.comments ?? '',
      destination_ref_mode: 'nullify',
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    let { destination_ref_mode, ...body } = values;
    let mutationValues = {
      body,
      searchParams:
        destination_ref_mode === undefined
          ? undefined
          : new URLSearchParams({ destination_ref_mode }),
    };
    mutation.mutate(mutationValues, {
      onSuccess: (data, _variables, _context) => {
        if (method === 'POST') {
          navigate({ to: `/nodes/${data.node_id}` });
        } else if (method === 'PATCH') {
          closeModals();
        }
      },
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes(`Host ID ${values.host_id}`)) {
            // This can only happen if someone fetches /api/hosts and
            // before they submit the form, the host was deleted.
            form.setFieldValue('host_id', null);
            form.setFieldError(
              'host_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('host_id'), false);
          } else if (
            error.detail.includes(`Operator ID ${values.operator_id}`)
          ) {
            // This can only happen if someone fetches /api/operators and
            // before they submit the form, the operator was deleted.
            form.setFieldValue('operator_id', null);
            form.setFieldError(
              'operator_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('operator_id'), false);
          } else if (
            error.detail.includes(`Allocator ID ${values.allocator_id}`)
          ) {
            // This can happen if someone fetches /api/allocators and
            // before they submit the form, the allocator was deleted.
            form.setFieldValue('allocator_id', null);
            form.setFieldError(
              'allocator_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('allocator_id'), false);
          } else {
            // Should never happen when creating
            // User opened edit page and node was deleted
            setErrorSection(
              `${error.detail} Something was likely deleted, refresh the page.`,
            );
            scrollToErrorSection();
          }
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.includes('cannot associate with an operator') ||
              error.detail.includes(
                `Operator ID ${values.operator_id} does not match host operator ID`,
              ):
              form.setFieldError('operator_id', error.detail);
              scrollElementIntoView(form.getInputNode('operator_id'), false);
              break;
            case error.detail.includes(
              `Node number ${values.node_number} is not allocated to operator ID`,
            ) ||
              (error.detail.includes(`FQNN`) &&
                error.detail.includes(`already used by`)):
              form.setFieldError('node_number', error.detail);
              scrollElementIntoView(form.getInputNode('node_number'));
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
              !firstErrorPath.includes('allocator_id'),
            );
          },
          // scrollAfterValidate(
          //   form,
          //   errors,
          //   accordionValues,
          //   setAccordionValues,
          // ),
        )}
      >
        <Fieldset legend="Fully Qualified Node Number (FQNN)">
          <FetchSelect
            label="Allocator ID"
            placeholder="Allocator ID"
            queryKey={['allocators']}
            url={`/api/allocators`}
            initialValue={
              initialNode
                ? initialNode.allocator
                : { allocator_id: '0', allocator_name: 'Default Allocator' }
            }
            handleFormat={formatAllocator}
            {...form.getInputProps('allocator_id')}
            key={form.key('allocator_id')}
          />
          <NumberInput
            withAsterisk
            label="Node number"
            placeholder="Node number"
            allowNegative={false}
            allowDecimal={false}
            mt="sm"
            {...form.getInputProps('node_number')}
            key={form.key('node_number')}
          />
        </Fieldset>
        <FetchSelect
          label="Host"
          placeholder="Host"
          queryKey={['hosts']}
          url={`/api/hosts`}
          initialValue={initialNode?.host}
          handleFormat={formatHost}
          mt="sm"
          {...form.getInputProps('host_id')}
          key={form.key('host_id')}
        />
        <FetchSelect
          label="Operator"
          description={`If an operator is used, the server will match the allocator ID for
            you.`}
          placeholder="Operator"
          queryKey={['operators']}
          url={`/api/operators`}
          initialValue={initialNode?.operator}
          handleFormat={formatOperator}
          mt="sm"
          {...form.getInputProps('operator_id')}
          key={form.key('operator_id')}
        />
        <NumberInput
          label="SDR working memory (byte)"
          placeholder="SDR working memory"
          allowNegative={false}
          allowDecimal={false}
          mt="sm"
          {...form.getInputProps('sdr_wm_size')}
          key={form.key('sdr_wm_size')}
        />
        <Checkbox.Group
          label="SDR configuration flags"
          description={`Not checking any flags means using whatever default flags
            that the node's version of ION uses`}
          mt="sm"
          {...form.getInputProps('sdr_config_flags')}
          key={form.key('sdr_config_flags')}
        >
          <Stack mt="sm">
            <Checkbox value="SDR_IN_DRAM" label="SDR_IN_DRAM" />
            <Checkbox value="SDR_IN_FILE" label="SDR_IN_FILE" />
            <Checkbox value="SDR_REVERSIBLE" label="SDR_REVERSIBLE" />
            <Checkbox value="SDR_BOUNDED" label="SDR_BOUNDED" />
          </Stack>
        </Checkbox.Group>
        <NumberInput
          label="Heap words"
          placeholder="Heap words"
          allowNegative={false}
          allowDecimal={false}
          mt="sm"
          {...form.getInputProps('heap_words')}
          key={form.key('heap_words')}
        />
        <NumberInput
          label="Working memory (byte)"
          placeholder="Working memory"
          allowNegative={false}
          allowDecimal={false}
          mt="sm"
          {...form.getInputProps('wm_size')}
          key={form.key('wm_size')}
        />
        <TextInput
          label="Node name"
          placeholder="Node name"
          description={`Name used by ION Config Tool to name config files.
            E.g., if a node's name is "node1",
            then the tool generates node1.bprc, node1.ionrc, etc.`}
          mt="sm"
          {...form.getInputProps('node_name')}
          key={form.key('node_name')}
        />
        <Textarea
          label="Comments"
          placeholder="Comments"
          autosize
          minRows={2}
          mt="sm"
          {...form.getInputProps('comments')}
          key={form.key('comments')}
        />
        {showDestRefMode &&
          form.getValues().host_id !== initialNode?.host?.host_id && (
            <>
              <DestinationRefModeRadio
                options={destination_ref_mode_options}
                destRefModeRadioDisabled={destRefModeRadioDisabled}
                form={form}
              />
              <Text c="dimmed" size="sm" mt="md">
                <strong>Note:</strong> when changing hosts, inducts and seats
                will drop references to links.
              </Text>
            </>
          )}

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

export default NodeForm;
