import {
  Box,
  Button,
  Fieldset,
  Group,
  NumberInput,
  Space,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useRef, useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import {
  formatAllocator,
  formatHost,
  formatOperator,
} from '../utils/formatFunctions';
import { useCopyNodeMutation } from '../utils/queries';
import {
  drill,
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';
import { DestinationRefModeRadio } from './DestinationRefModeRadio';

const destination_ref_mode_options = [
  {
    name: 'nullify',
    description: `Copied inducts and seats will not reference destinations.`,
  },
  {
    name: 'associate',
    description: `Copied inducts and seats will reference equivalent
      destinations under the new host if they exist, otherwise the induct or
      seat will not reference a destination.`,
  },
  {
    name: 'copy',
    description: `Copied inducts and seats will reference equivalent
      destinations under the new host if they exist. If an equivalent
      destination does not exist, then the destination is copied to the new host`,
  },
];

export function NodeCopy({ node, closeModals }) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const [showDestRefMode, setShowDestRefMode] = useState(false);
  const [destRefModeRadioDisabled, setDestRefModeRadioDisabled] = useState(
    node.host === null,
  );
  const navigate = useNavigate();
  const mutation = useCopyNodeMutation(node.node_id);
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      allocator_id: undefined,
      node_number: undefined,
      host_id: undefined,
      operator_id: undefined,
      destination_ref_mode: undefined,
    },

    initialDirty: {
      allocator_id: true,
      node_number: true,
      host_id: true,
      operator_id: true,
      destination_ref_mode: true,
    },

    // TOOD: do we need this??
    enhanceGetInputProps: ({ field, options, form }) => {
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
            ? `Node number must be between 0 and ${2 ** 32 - 1}.`
            : null,
    },

    transformValues: (values) => {
      let res = JSON.parse(JSON.stringify(values));
      if (res.operator_id !== null) {
        delete res.allocator_id;
      }
      return res;
    },
  });
  form.watch('host_id', ({ value, _dirty }) => {
    if (node.host) {
      // Only show radio buttons if to-be-copied node has a host.
      if (value === null) {
        form.setFieldValue('destination_ref_mode', 'nullify');
        setDestRefModeRadioDisabled(true);
      } else {
        setDestRefModeRadioDisabled(false);
      }
      if (value === `${node.host.host_id}`) {
        form.setFieldValue('destination_ref_mode', 'copy');
      }
      setShowDestRefMode(true);
    } else {
      setShowDestRefMode(false);
    }
  });

  if (!initializedFormValues.current) {
    form.setValues({
      allocator_id: '0',
      node_number: '',
      host_id: null,
      operator_id: null,
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
      onSuccess: (data) => {
        navigate({ to: `/nodes/${data.node_id}` });
        closeModals();
      },
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes(`Host ID`)) {
            // This can only happen if someone fetches /api/hosts and
            // before they submit the form, the host was deleted.
            form.setFieldValue('host_id', null);
            form.setFieldError(
              'host_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('host_id'), false);
          } else if (error.detail.includes(`Operator ID`)) {
            // This can only happen if someone fetches /api/operators and
            // before they submit the form, the operator was deleted.
            form.setFieldValue('operator_id', null);
            form.setFieldError(
              'operator_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('operator_id'), false);
          } else if (error.detail.includes(`Allocator ID`)) {
            // This can happen if someone fetches /api/allocators and
            // before they submit the form, the allocator was deleted.
            form.setFieldValue('allocator_id', null);
            form.setFieldError(
              'allocator_id',
              `${error.detail} Something was likely deleted.`,
            );
            scrollElementIntoView(form.getInputNode('allocator_id'), false);
          } else {
            // If the node to be copied was deleted
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
      <Text c="dimmed" size="sm">
        Fill out this form to create a copy of node (
        {node.allocator.allocator_id}, {node.node_number}), node ID{' '}
        {node.node_id}.<br />
        <strong>Note:</strong> point of contact information is not copied.
      </Text>
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
        )}
      >
        <Fieldset legend="Fully Qualified Node Number (FQNN)">
          <FetchSelect
            label="Allocator ID"
            placeholder="Allocator ID"
            queryKey={['allocators']}
            url={`/api/allocators`}
            initialValue={{
              allocator_id: '0',
              allocator_name: 'Default Allocator',
            }}
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
          initialValue={null}
          handleFormat={formatHost}
          mt="sm"
          {...form.getInputProps('host_id')}
          key={form.key('host_id')}
        />
        <FetchSelect
          label="Operator"
          description={`If an operator is used, the server will match the
            allocator ID for you.`}
          placeholder="Operator"
          queryKey={['operators']}
          url={`/api/operators`}
          initialValue={null}
          handleFormat={formatOperator}
          mt="sm"
          {...form.getInputProps('operator_id')}
          key={form.key('operator_id')}
        />
        {showDestRefMode && form.getValues().host_id !== null && (
          <>
            <DestinationRefModeRadio
              options={destination_ref_mode_options}
              destRefModeRadioDisabled={destRefModeRadioDisabled}
              form={form}
            />
            <Text c="dimmed" size="sm" mt="md">
              <strong>Note:</strong> link references for inducts and seats are
              only kept if copying to the same host.
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
