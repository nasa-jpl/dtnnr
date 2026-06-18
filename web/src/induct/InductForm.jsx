import {
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Fieldset,
  Group,
  NumberInput,
  Radio,
  Select,
  Space,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import {
  formatDestination,
  formatGeneralError,
} from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

function formatClProtocolForInductForm(clProtocol) {
  if (!clProtocol) {
    return null;
  }
  return {
    value: `${clProtocol.cl_protocol_id} ${clProtocol.cl_protocol_name}`,
    label: `[${clProtocol.cl_protocol_id}] ${clProtocol.cl_protocol_name}`,
  };
}

function getClProtocolNameFromValue(value) {
  if (!value) {
    return null;
  }
  return value.substring(value.indexOf(' ') + 1);
}

function getClProtocolIdFromValue(value) {
  if (!value) {
    return null;
  }
  return value.substring(0, value.indexOf(' '));
}

const knownCLI = [
  'brsccla',
  'brsscla',
  'bsspcli',
  'dccpcli',
  'dgrcli',
  'ltpcli',
  'stcpcli',
  'tcpcli',
  'udpcli',
];

const cliNotUsingLTP = [
  'brsccla',
  'brsscla',
  'bsspcli',
  'dccpcli',
  'dgrcli',
  'stcpcli',
  'tcpcli',
  'udpcli',
];

const validateDuctName = {
  type: (value, values) => {
    if (value === 'ip' && values.cli_command === 'brsccla') {
      // form.watch() should prevent this condition
      return 'brsccla cannot be used with an IP duct name';
    }
    return null;
  },
  ip: {
    port_number: (value, values) =>
      (value !== '' && values.duct_name.type === 'ip' && Number(value) < 0) ||
      Number(value) > 65535
        ? 'Value must be between 0 and 65535'
        : null,
  },
};

function validateCliCommand(value, values) {
  const cliToProtocolName = {
    brsccla: 'brsc',
    brsscla: 'brss',
    bsspcli: 'bssp',
    dccpcli: 'dccp',
    dgrcli: 'dgr',
    ltpcli: 'ltp',
    stcpcli: 'stcp',
    tcpcli: 'tcp',
    udpcli: 'udp',
  };
  const protocolName = getClProtocolNameFromValue(values.cl_protocol_str);
  if (
    Object.hasOwn(cliToProtocolName, value) &&
    cliToProtocolName[value] !== protocolName
  ) {
    return `CLI program ${value} must use an induct with a protocol name of
      "${cliToProtocolName[value]}"`;
  }
  return null;
}

function validateUsesLtp(value, values) {
  if (!value && values.cli_command === 'ltpcli') {
    // form.watch() should prevent this condition
    return 'ltpcli requires noting that the induct uses LTP';
  }
  if (value && cliNotUsingLTP.includes(values.cli_command)) {
    // form.watch() should prevent this condition
    return `${value} requires noting that the induct does not use LTP`;
  }
  return null;
}

function transformValuesDuctName(values) {
  if (['bsspcli', 'ltpcli'].includes(values.cli_command)) {
    return null;
  }
  if (values.duct_name.type === 'plain') {
    return values.duct_name.value ? values.duct_name.value : null;
  }
  if (values.duct_name.type === 'ip') {
    return {
      type: 'ip',
      destination_id: values.duct_name.ip.destination_id,
      port_number:
        values.duct_name.ip.port_number !== ''
          ? values.duct_name.ip.port_number
          : null,
    };
  }
}

function transformInductExtra({ message, key, source }) {
  if (key === 'cl_protocol_id') {
    return { key: 'cl_protocol_str', message, source };
  }
  if (key === 'duct_name') {
    return { key: 'duct_name.value', message, source };
  }
  return { message, key, source };
}

const cliWithDisabledDuctType = ['bsspcli', 'ltpcli', 'brsccla'];
const cliWithDisabledDuctValue = ['bsspcli', 'ltpcli'];

export function InductForm({
  nodeId,
  allocatorId,
  nodeNumber,
  hostId,
  initialInduct,
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
      // cl_protocol_str is ID + name; we need name to do client-side validation,
      // and ID to use API
      cl_protocol_str: undefined,
      duct_name: {
        type: undefined,
        // value is for string
        value: undefined,
        ip: {
          destination_id: undefined,
          port_number: undefined,
        },
      },
      cli_command: undefined,
      uses_ltp: undefined,
    },

    initialDirty: {
      cl_protocol_str: true,
      duct_name: {
        type: true,
        value: true,
        ip: {
          destination_id: true,
          port_number: true,
        },
      },
      cli_command: true,
      uses_ltp: true,
    },

    validate: {
      duct_name: validateDuctName,
      cli_command: validateCliCommand,
      uses_ltp: validateUsesLtp,
    },

    // transformValues is called after validation
    transformValues: (values) => ({
      cl_protocol_id: getClProtocolIdFromValue(values.cl_protocol_str),
      duct_name: transformValuesDuctName(values),
      cli_command: values.cli_command !== '' ? values.cli_command : null,
      uses_ltp: values.uses_ltp,
    }),
  });
  const [ductType, setDuctType] = useState('');
  const [ductTypeDisabled, setDuctTypeDisabled] = useState(false);
  const [ductValueDisabled, setDuctValueDisabled] = useState(false);
  const [usesLTPDisabled, setUsesLTPDisabled] = useState(false);

  if (!initializedFormValues.current) {
    let values = {
      cl_protocol_str:
        formatClProtocolForInductForm(initialInduct?.cl_protocol)?.value ?? '',
      duct_name: {
        type: initialInduct?.duct_name?.type ?? 'plain',
        value:
          initialInduct?.duct_name?.type === 'plain'
            ? initialInduct.duct_name.value
            : null,
        ip: {
          destination_id:
            initialInduct?.duct_name?.destination?.destination_id ?? null,
          port_number: initialInduct?.duct_name?.port_number ?? '',
        },
      },
      cli_command: initialInduct?.cli_command ?? '',
      uses_ltp: initialInduct?.uses_ltp ?? false,
    };
    form.setValues(values);
    setDuctType(values.duct_name.type);
    setDuctTypeDisabled(cliWithDisabledDuctType.includes(values.cli_command));
    setDuctValueDisabled(cliWithDisabledDuctValue.includes(values.cli_command));
    setUsesLTPDisabled(cliNotUsingLTP.includes(values.cli_command));
    initializedFormValues.current = true;
  }

  form.watch('duct_name.type', ({ value }) => setDuctType(value));
  form.watch('cli_command', ({ value }) => {
    if (value === 'ltpcli') {
      form.setFieldValue('uses_ltp', true);
      setUsesLTPDisabled(true);
    } else if (cliNotUsingLTP.includes(value)) {
      form.setFieldValue('uses_ltp', false);
      setUsesLTPDisabled(true);
    } else {
      setUsesLTPDisabled(false);
    }

    if (cliWithDisabledDuctType.includes(value)) {
      form.setFieldValue('duct_name.type', 'plain');
      setDuctTypeDisabled(true);
      if (cliWithDisabledDuctValue.includes(value)) {
        // As of ION 4.1.4-b.2, ltpclo suppots allocator_id.node_number whlie
        // bsspclo doesn't.
        // These values are what the user should use in ION, but the DTNNR API
        // only accpets `null` since these details can be derived from the
        // node.
        if (value === 'ltpcli') {
          form.setFieldValue('duct_name.value', `${allocatorId}.${nodeNumber}`);
        } else if (value === 'bsspcli') {
          form.setFieldValue(
            'duct_name.value',
            `${(BigInt(allocatorId) << BigInt(32)) + BigInt(nodeNumber)}`,
          );
        }
        setDuctValueDisabled(true);
      } else {
        setDuctValueDisabled(false);
      }
    } else {
      setDuctTypeDisabled(false);
      setDuctValueDisabled(false);
    }
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Node ID')) {
            // For creating
            queryClient.invalidateQueries({ queryKey: ['nodes', nodeId] });
            setErrorSection(
              `${error.detail}. Node was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('Induct ID')) {
            // For editing
            queryClient.invalidateQueries({
              queryKey: ['nodes', nodeId, 'inducts'],
            });
            setErrorSection(
              `${error.detail}. Induct was deleted, refresh the table.`,
            );
          } else if (error.detail.includes('CL protocol ID')) {
            queryClient.invalidateQueries({
              queryKey: ['nodes', nodeId, 'cl-protocols'],
            });
            setErrorSection(
              `${error.detail}. CL protocol was deleted, refresh the form.`,
            );
          } else if (error.detail.includes('Destination ID')) {
            queryClient.invalidateQueries({
              queryKey: ['hosts', hostId, 'destinations'],
            });
            setErrorSection(
              `${error.detail}. Destination was deleted or no longer accessible,` +
                ' refresh the page.',
            );
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
        } else if (error.status === 400) {
          switch (true) {
            case error.title === 'Validation Error': {
              setAndScrollForExtra(form, error.extra.map(transformInductExtra));
              break;
            }
            case error.detail.includes('CL protocol ID'):
              form.setFieldError('cl_protocol_str', error.detail);
              scrollElementIntoView(form.getInputNode('cl_protocol_str'));
              break;
            case error.detail.toLowerCase().includes('destination'):
              form.setFieldError('duct_name.ip.destination_id', error.detail);
              scrollElementIntoView(
                form.getInputNode('duct_name.ip.destination_id'),
              );
              break;
            case error.detail.startsWith('Cannot change `uses_ltp`'):
              form.setFieldError(
                'uses_ltp',
                `${error.detail.split('.')[0]} (IDs: ${error.extra.join(', ')})`,
              );
              scrollElementIntoView(form.getInputNode('uses_ltp'));
              break;
            case error.detail.includes('cli_command') &&
              error.detail.includes('must be associated with'):
              form.setFieldError('cl_protocol_str', error.detail);
              scrollElementIntoView(form.getInputNode('cl_protocol_str'));
              break;
            case error.detail.includes('`uses_ltp` must be'):
              form.setFieldError('uses_ltp', error.detail);
              scrollElementIntoView(form.getInputNode('uses_ltp'));
              break;
            case error.detail.includes('`duct_name` must be null'):
              form.setFieldError('duct_name.value', error.detail);
              scrollElementIntoView(form.getInputNode('duct_name.value'));
              break;
            case error.detail.includes(
              '"ip" type object cannot be used for `duct_name`',
            ):
              form.setFieldError('duct_name.type', error.detail);
              scrollElementIntoView(form.getInputNode('duct_name.type'));
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
            scrollElementIntoView(
              form.getInputNode(firstErrorPath),
              ![
                // For custom CLIs that don't match one of the values in the
                // Select, focusing on the cli_command would be helpful. In
                // other cases it's bad because the dropdown covers the error
                // message. But logic to do that is messy, so let's just never
                // focus.
                'cli_command',
                'duct_name.value',
                'duct_name.ip.port_number',
              ].includes(firstErrorPath),
            );
          },
        )}
      >
        <FetchSelect
          label="CL protocol"
          placeholder="CL protocol"
          queryKey={['nodes', nodeId, 'cl-protocols']}
          url={`/api/nodes/${nodeId}/cl-protocols`}
          initialValue={initialInduct?.cl_protocol}
          handleFormat={formatClProtocolForInductForm}
          {...form.getInputProps('cl_protocol_str')}
          key={form.key('cl_protocol_str')}
        />
        <Autocomplete
          label="Convergence layer input command"
          placeholder="Convergence layer input command"
          mt="sm"
          data={knownCLI}
          {...form.getInputProps('cli_command')}
          key={form.key('cli_command')}
        />
        <Checkbox
          label="Uses LTP"
          description={`Check if CLI uses LTP. Seats can only associate with this
            induct if this is checked.`}
          mt="sm"
          disabled={usesLTPDisabled}
          {...form.getInputProps('uses_ltp', { type: 'checkbox' })}
          key={form.key('uses_ltp')}
        />
        <Fieldset legend="Duct name" mt="sm">
          <Radio.Group
            name="type"
            label="Duct type"
            disabled={ductTypeDisabled}
            {...form.getInputProps('duct_name.type')}
            key={form.key('duct_name.type')}
          >
            <Group>
              <Radio value="plain" label="Plain" />
              <Radio value="ip" label="IP" />
            </Group>
          </Radio.Group>
          {ductType === 'plain' && (
            <TextInput
              label="Value"
              placeholder="Value"
              disabled={ductValueDisabled}
              mt="sm"
              {...form.getInputProps('duct_name.value')}
              key={form.key('duct_name.value')}
            />
          )}
          {ductType === 'ip' && (
            <>
              <Text c="dimmed" size="xs" mt="sm">
                The IP type is used for duct names with the format "ip[:port]",
                where "ip" is the destination value of the chosen destination.
              </Text>
              {hostId === null || hostId === undefined ? (
                <Select
                  label="Destination"
                  description="Node must be associated with a host to select destination"
                  placeholder="Destination"
                  disabled
                  mt="sm"
                  {...form.getInputProps('duct_name.ip.destination_id')}
                  key={form.key('duct_name.ip.destination_id')}
                />
              ) : (
                <FetchSelect
                  label="Destination"
                  placeholder="Destination"
                  queryKey={['hosts', hostId, 'destinations']}
                  url={`/api/hosts/${hostId}/destinations`}
                  initialValue={null}
                  handleFormat={formatDestination}
                  mt="sm"
                  {...form.getInputProps('duct_name.ip.destination_id')}
                  key={form.key('duct_name.ip.destination_id')}
                />
              )}
              <NumberInput
                label="Port number"
                placeholder="Port number"
                allowNegative={false}
                allowDecimal={false}
                mt="sm"
                min={0}
                max={65535}
                {...form.getInputProps('duct_name.ip.port_number')}
                key={form.key('duct_name.ip.port_number')}
              />
            </>
          )}
        </Fieldset>
        <Group justify="flex-end" mt="md">
          <Button type="submit">Submit</Button>
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
