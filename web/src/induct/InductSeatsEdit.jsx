import {
  Alert,
  Box,
  Button,
  Group,
  Loader,
  LoadingOverlay,
  Space,
  Stack,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useRef, useState } from 'react';
import { FetchMultiSelect } from '../components/FetchMultiSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError, formatSeat } from '../utils/formatFunctions';
import {
  useInductSeatAllQuery,
  useReplaceInductSeatMutation,
} from '../utils/queries';
import { scrollElementIntoView, scrollToErrorSection } from '../utils/util';

export function InductSeatsEdit({ inductId, nodeId, closeModals }) {
  const initializedFormValues = useRef(false);
  const mutation = useReplaceInductSeatMutation(inductId);
  const [errorSection, setErrorSection] = useState('');
  const { isPending, isError, data, error } = useInductSeatAllQuery(inductId);
  const form = useForm({
    mode: 'uncontrolled',
    initialValues: { seat_ids: undefined },
    initialDirty: { seat_ids: true },
    // TODO: backend should restrict how many IDs you can send.
    // When it does, do client-side validation.
  });

  if (!initializedFormValues.current && !isPending) {
    form.setValues({ seat_ids: data?.items?.map((s) => s.seat_id) ?? [] });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values.seat_ids, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Induct ID')) {
            setErrorSection(
              `Induct ID ${inductId} does not exist.` +
                ' The induct has likely been deleted. Refresh the table.',
            );
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.detail.includes('does not use LTP'):
              setErrorSection(
                `${error.detail}. The induct was likely updated.` +
                  ' Refresh the table.',
              );
              scrollToErrorSection();
              break;
            case error.detail.includes('`extra`'):
              form.setFieldError(
                'seat_ids',
                'Seat IDs that are not associated with the node were sent.' +
                  ' The seats were likely deleted. Refresh the table.',
              );
              scrollElementIntoView(form.getInputNode('seat_ids'));
              break;
            default:
              // Unexpected error
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
      <LoadingOverlay
        visible={isPending}
        loaderProps={{
          children: (
            <Stack align="center" justify="center">
              <Loader />
              <Text>Loading associated seats</Text>
            </Stack>
          ),
        }}
      />
      <Text c="dimmed" size="sm">
        Select seats to associate with the induct. The chosen seats will{' '}
        <em>replace</em> the existing associations.
      </Text>
      <Space h="md" />
      <form onSubmit={form.onSubmit((values) => handleSubmit(form, values))}>
        <FetchMultiSelect
          label="Seats"
          placeholder="Select seats"
          queryKey={['nodes', nodeId, 'seats', 'select']}
          url={`/api/nodes/${nodeId}/seats`}
          initialValue={data?.items}
          handleFormat={formatSeat}
          // maxValues TODO
          {...form.getInputProps('seat_ids')}
          key={form.key('seat_ids')}
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
        {isError && (
          <>
            <Space h="md" />
            <Alert variant="light" color="red" title="Error">
              Failed to load associated seats. {formatGeneralError(error)}
            </Alert>
          </>
        )}
      </form>
    </Box>
  );
}
