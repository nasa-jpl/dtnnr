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
import {
  formatGeneralError,
  formatLinkForForm,
} from '../utils/formatFunctions';
import {
  useReplaceSeatLinkMutation,
  useSeatLinkAllQuery,
} from '../utils/queries';
import { scrollElementIntoView, scrollToErrorSection } from '../utils/util';

export function SeatLinksEdit({ seatId, hostId, closeModals }) {
  const initializedFormValues = useRef(false);
  const mutation = useReplaceSeatLinkMutation(seatId);
  const [errorSection, setErrorSection] = useState('');
  const { isPending, isError, data, error } = useSeatLinkAllQuery(seatId);
  const form = useForm({
    mode: 'uncontrolled',
    initialValues: { link_ids: undefined },
    initialDirty: { link_ids: true },
    // TODO: backend should restrict how many IDs you can send.
    // When it does, do client-side validation.
  });

  if (!initializedFormValues.current && !isPending) {
    form.setValues({ link_ids: data?.items?.map((l) => l.link_id) ?? [] });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values.link_ids, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Seat ID')) {
            setErrorSection(
              `Seat ID ${seatId} does not exist.` +
                ' The seat has likely been deleted. Refresh the table.',
            );
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.detail.includes('not associated with a host'):
              setErrorSection(
                `${error.detail}. The node was likely updated.` +
                  ' Refresh the page.',
              );
              scrollToErrorSection();
              break;
            case error.detail.includes('`extra`') &&
              error.detail.includes('direction'):
              form.setFieldError(
                'link_ids',
                `Link IDs of simplex outgoing links were sent which is not allowed.
                The links were likely updated. Refresh the table.`,
              );
              scrollElementIntoView(form.getInputNode('link_ids'));
              break;
            case error.detail.includes('`extra`') &&
              error.detail.includes('host ID'):
              form.setFieldError(
                'link_ids',
                `Link IDs that are not associated with the host were sent.
                The links were likely deleted. Refresh the table.`,
              );
              scrollElementIntoView(form.getInputNode('link_ids'));
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
              <Text>Loading associated links</Text>
            </Stack>
          ),
        }}
      />
      <Text c="dimmed" size="sm">
        Select links to associate with the seat. The chosen links will{' '}
        <em>replace</em> the existing associations.
      </Text>
      <Space h="md" />
      <form onSubmit={form.onSubmit((values) => handleSubmit(form, values))}>
        <FetchMultiSelect
          label="Links"
          placeholder="Select links"
          queryKey={['hosts', hostId, 'links', 'select']}
          url={`/api/hosts/${hostId}/links`}
          initialValue={data?.items}
          handleFormat={formatLinkForForm}
          // TODO: server-side filtering
          processData={(data) =>
            data?.items?.filter((l) => l.direction !== 'Simplex (outgoing)')
          }
          // maxValues TODO
          {...form.getInputProps('link_ids')}
          key={form.key('link_ids')}
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
              Failed to load associated links. {formatGeneralError(error)}
            </Alert>
          </>
        )}
      </form>
    </Box>
  );
}
