import {
  Box,
  Button,
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

export function SeatForm({
  nodeId,
  hostId,
  initialSeat,
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
      lsi_command: undefined,
      seat_ip: {
        destination_id: undefined,
        port_number: undefined,
      },
    },

    initialDirty: {
      lsi_command: true,
      seat_ip: {
        destination_id: true,
        port_number: true,
      },
    },
  });
  const [seatType, setSeatType] = useState('plain');

  if (!initializedFormValues.current) {
    if (initialSeat === undefined) {
      form.setValues({
        lsi_command: '',
        seat_ip: { destination_id: null, port_number: null },
      });
    } else {
      let values = {
        lsi_command: initialSeat.lsi_command,
        seat_ip:
          initialSeat.seat_ip === null
            ? null
            : {
                destination_id:
                  initialSeat.seat_ip?.destination?.destination_id ?? null,
                port_number: initialSeat.seat_ip.port_number,
              },
      };
      form.setValues(values);
      setSeatType(initialSeat.seat_ip === null ? 'plain' : 'ip');
    }
    initializedFormValues.current = true;
  }

  // whether seat_ip is sent should be determined in this function
  async function handleSubmit(form, values) {
    let valuesToSubmit = {
      ...values,
      seat_ip: seatType === 'plain' ? null : values.seat_ip,
    };
    mutation.mutate(valuesToSubmit, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Node ID')) {
            // For creating
            queryClient.invalidateQueries({ queryKey: ['nodes', nodeId] });
            setErrorSection(
              `${error.detail}. Node was deleted, refresh the page.`,
            );
          } else if (error.detail.includes('Seat ID')) {
            // For editing
            queryClient.invalidateQueries({
              queryKey: ['nodes', nodeId, 'seats'],
            });
            setErrorSection(
              `${error.detail}. Seat was deleted, refresh the table.`,
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
            case error.detail.toLowerCase().includes('destination'):
              form.setFieldError('seat_ip.destination_id', error.detail);
              scrollElementIntoView(
                form.getInputNode('seat_ip.destination_id'),
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
      <form onSubmit={form.onSubmit((values) => handleSubmit(form, values))}>
        <Fieldset legend="LSI command">
          <Radio.Group
            value={seatType}
            onChange={setSeatType}
            name="type"
            label="Seat type"
          >
            <Group>
              <Radio value="plain" label="Plain" />
              <Radio value="ip" label="IP" />
            </Group>
          </Radio.Group>
          <TextInput
            label="LSI command"
            placeholder="LSI command"
            mt="sm"
            {...form.getInputProps('lsi_command')}
            key={form.key('lsi_command')}
          />
          {seatType === 'ip' && (
            <>
              <Text c="dimmed" size="xs" mt="sm">
                The IP type is used for LSI commands that end with an argument
                in the form "ip[:port]", where "ip" is the destination value of
                the chosen destination.
              </Text>
              {hostId === null || hostId === undefined ? (
                <Select
                  label="Destination"
                  description="Node must be associated with a host to select destination"
                  placeholder="Destination"
                  disabled
                  mt="sm"
                  {...form.getInputProps('seat_ip.destination_id')}
                  key={form.key('seat_ip.destination_id')}
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
                  {...form.getInputProps('seat_ip.destination_id')}
                  key={form.key('seat_ip.destination_id')}
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
                {...form.getInputProps('seat_ip.port_number')}
                key={form.key('seat_ip.port_number')}
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
