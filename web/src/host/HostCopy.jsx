import { Box, Button, Group, Space, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useNavigate } from '@tanstack/react-router';
import { useRef, useState } from 'react';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError, formatOperator } from '../utils/formatFunctions';
import { useCopyHostMutation } from '../utils/queries';
import {
  flatten,
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';
import { NodeCopyPaper } from './NodeCopyPaper';

export function HostCopy({ host, closeModals }) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const navigate = useNavigate();
  const mutation = useCopyHostMutation(host.host_id);
  const form = useForm({
    mode: 'uncontrolled',

    // Mantine form re-renders when dirty field status changes. Force it to
    // always be dirty. No input can change a field back to `undefined`.
    initialValues: {
      operator_id: undefined,
      nodes:
        host?.nodes?.map(() => ({
          node_id: undefined,
          allocator_id: undefined,
          node_number: undefined,
          operator_id: undefined,
          active: undefined,
        })) ?? undefined,
    },

    initialDirty: {
      operator_id: true,
      ...(host
        ? flatten(
            host.nodes.map(() => ({
              allocator_id: true,
              node_number: true,
              operator_id: true,
            })),
            'nodes',
          )
        : { nodes: true }),
    },

    validate: {
      nodes: {
        allocator_id: (value, values, path) => {
          let index = Number(path.split('.')[1]);
          return values.nodes[index].active &&
            value === null &&
            values.nodes[index].operator_id === null
            ? 'Allocator ID may not be empty.'
            : null;
        },
        node_number: (value, values, path) => {
          let index = Number(path.split('.')[1]);
          if (!values.nodes[index].active) {
            return null;
          } else if (value === '') {
            return 'Node number may not be empty.';
          } else if (Number(value) < 0 || Number(value) > 2 ** 32 - 1) {
            return `Node number must be between 0 and ${2 ** 32 - 1}.`;
          }
          return null;
        },
        operator_id: (value, values, path) => {
          let index = Number(path.split('.')[1]);
          return values.nodes[index].active &&
            value !== null &&
            value !== values.operator_id
            ? "Operator ID must match with host's operator ID."
            : null;
        },
      },
    },

    transformValues: (values) => {
      // Deep copy since `nodes` is an array of objects
      let res = JSON.parse(JSON.stringify(values));
      res.nodes = res.nodes.filter((n) => n.active);
      res.nodes.forEach((n) => {
        delete n.active;
      });
      return res;
    },
  });

  if (host && !initializedFormValues.current) {
    form.setValues({
      operator_id: null,
      nodes: host.nodes.map((n) => ({
        node_id: n.node_id,
        allocator_id: '0',
        node_number: '',
        operator_id: null,
        active: true,
      })),
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: (data) => {
        navigate({ to: `/hosts/${data.host_id}` });
        closeModals();
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
            // Host to be copied was deleted
            setErrorSection(
              `${error.detail}. Something was likely deleted, refresh the page.`,
            );
            scrollToErrorSection();
          }
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
            // fall through
            case error.detail.includes('violate the rules for copying nodes'):
              setAndScrollForExtra(form, error.extra);
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
        Fill out this form to create a copy of the host identified by host ID{' '}
        {host.host_id}.<br />
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
              firstErrorPath.includes('node_number'),
            );
          },
        )}
      >
        <FetchSelect
          label="Operator"
          placeholder="Null"
          queryKey={['operators']}
          url={`/api/operators`}
          initialValue={null}
          handleFormat={formatOperator}
          mt="sm"
          {...form.getInputProps('operator_id')}
          key={form.key('operator_id')}
        />
        {host.nodes.length > 0 && (
          <Text c="dimmed" size="sm" mt="sm">
            Pick nodes to copy. If the copied host is under an operator, then
            your copied nodes must either be under the same operator or under no
            operator.
          </Text>
        )}
        {host.nodes.map((item, index) => (
          <NodeCopyPaper
            form={form}
            node_id={item.node_id}
            allocator_id={item.allocator.allocator_id}
            node_number={item.node_number}
            index={index}
            key={item.node_id}
          />
        ))}

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
