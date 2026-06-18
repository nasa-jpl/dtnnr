import {
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Group,
  Space,
  Stack,
  Text,
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

const BP_BEST_EFFORT = 'BP_BEST_EFFORT';
const BP_RELIABLE = 'BP_RELIABLE';
const CL_NAME_CLASS_MAP = new Map();
CL_NAME_CLASS_MAP.set('udp', [BP_BEST_EFFORT]);
for (const c of ['tcp', 'stcp', 'dgr', 'dccp', 'brss', 'brsc']) {
  CL_NAME_CLASS_MAP.set(c, [BP_RELIABLE]);
}
for (const c of ['bssp', 'ltp', 'bibe']) {
  CL_NAME_CLASS_MAP.set(c, [BP_BEST_EFFORT, BP_RELIABLE]);
}

export function ClProtocolForm({
  initialProtocol,
  nodeId,
  closeModals,
  mutation,
  formDescription,
}) {
  const initializedFormValues = useRef(false);
  const [classDisabled, setClassDisabled] = useState(
    CL_NAME_CLASS_MAP.has(initialProtocol?.cl_protocol_name),
  );
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();

  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      cl_protocol_name: undefined,
      cl_protocol_class: undefined,
    },

    initialDirty: {
      cl_protocol_name: true,
      cl_protocol_class: true,
    },

    validate: {
      cl_protocol_name: (value) => {
        const encoder = new TextEncoder();
        const nameLength = encoder.encode(value).length;
        if (nameLength < 1 || nameLength > 15) {
          return 'Name length must be between 1 and 15 bytes';
        }
        return null;
      },
      cl_protocol_class: (value, values) => {
        if (value.length === 0) {
          return `Must specify at least one value`;
        }
        // Redundant since our form.watch() should force this value to be
        // correct if a known cl_protocol_name is used.
        if (
          CL_NAME_CLASS_MAP.has(values.cl_protocol_name) &&
          JSON.stringify(value.toSorted()) !==
            JSON.stringify(
              CL_NAME_CLASS_MAP.get(values.cl_protocol_name).toSorted(),
            )
        ) {
          return `A name of '${values.cl_protocol_name}' must use
            ${CL_NAME_CLASS_MAP.get(values.cl_protocol_name)}`;
        }
        return null;
      },
    },
  });

  if (!initializedFormValues.current) {
    form.setValues({
      cl_protocol_name: initialProtocol?.cl_protocol_name ?? '',
      cl_protocol_class: initialProtocol?.cl_protocol_class ?? [],
    });
    initializedFormValues.current = true;
  }

  form.watch('cl_protocol_name', ({ value }) => {
    if (CL_NAME_CLASS_MAP.has(value)) {
      form.setFieldValue('cl_protocol_class', CL_NAME_CLASS_MAP.get(value));
      setClassDisabled(true);
    } else {
      setClassDisabled(false);
    }
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          // For creating: when someone is on the node's details page and someone
          // deleted the node.
          if (error.detail.includes('Node ID')) {
            queryClient.invalidateQueries({ queryKey: ['nodes', nodeId] });
            setErrorSection(
              `${error.detail}. Node was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('CL protocol ID')) {
            // For editing: the CL protocol was deleted while editing
            queryClient.invalidateQueries({
              queryKey: ['nodes', nodeId, 'cl-protocols'],
            });
            setErrorSection(
              `${error.detail}. CL protocol was deleted, refresh the table.`,
            );
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.title === 'Validation Error':
              setAndScrollForExtra(form, error.extra);
              break;
            case error.detail.startsWith('`extra`'):
              form.setFieldError(
                'cl_protocol_name',
                'There are inducts that have a `cli_command` that rely on the' +
                  ` \`cl_protocol_name\` being ${initialProtocol.cl_protocol_name}`,
              );
              setErrorSection(
                'Remove or update these inducts to use a different CLI command' +
                  ' before `cl_protocol_name` can be safely updated:' +
                  ` ${JSON.stringify(error.extra)}`,
              );
              break;
            case error.detail.startsWith('A CL protocol'):
              form.setFieldError('cl_protocol_name', error.detail);
              break;
            default:
              // Unexpected error (wrong name + class should've been caught
              // by our validation above)
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
        {/* TODO: consider stripping whitespace of name? */}
        <Autocomplete
          label="CL protocol name"
          description={`If you're using a CLI that comes with ION, make sure to
            strip whitespace. The protocol name must exactly match one in the
            dropdown or the CLI will fail.`}
          placeholder={`Pick value or enter anything within 15 bytes.`}
          withAsterisk
          data={Array.from(CL_NAME_CLASS_MAP.keys()).toSorted()}
          {...form.getInputProps('cl_protocol_name')}
          key={form.key('cl_protocol_name')}
        />
        <Checkbox.Group
          label="CL protocol class"
          description={`A set of values that describes the reliability of the
            CL protocol. For certain protocol names, ION requires a specific
            class, so the checkboxes will be disabled.`}
          withAsterisk
          mt="sm"
          {...form.getInputProps('cl_protocol_class')}
          key={form.key('cl_protocol_class')}
        >
          <Stack mt="sm">
            <Checkbox
              value={BP_BEST_EFFORT}
              label="Best-effort"
              disabled={classDisabled}
            />
            <Checkbox
              value={BP_RELIABLE}
              label="Reliable"
              disabled={classDisabled}
            />
          </Stack>
        </Checkbox.Group>
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
