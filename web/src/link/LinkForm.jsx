import {
  Box,
  Button,
  Fieldset,
  Group,
  Radio,
  Select,
  Space,
  Stack,
  Text,
} from '@mantine/core';
import { createFormContext, hasLength } from '@mantine/form';
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { FetchMultiSelect } from '../components/FetchMultiSelect';
import FetchSelect from '../components/FetchSelect';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import {
  formatBand,
  formatGeneralError,
  formatUnderlyingCommService,
} from '../utils/formatFunctions';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';

const [FormProvider, useLinkFormContext, useLinkForm] = createFormContext();

function LinkRfField(initialLink) {
  const form = useLinkFormContext();
  const [typeValue, setTypeValue] = useState(form.getValues().type);

  form.watch('type', ({ value }) => {
    setTypeValue(value);
  });

  if (typeValue === 'rf') {
    return (
      <Fieldset legend="Radio specific fields" mt="sm">
        <FetchSelect
          label="Band"
          placeholder="Band"
          queryKey={['bands']}
          url={`/api/bands`}
          initialValue={initialLink?.link_rf?.band_id}
          handleFormat={formatBand}
          {...form.getInputProps('band_id')}
          key={form.key('band_id')}
        />
      </Fieldset>
    );
  }
}

export function LinkForm({
  initialLink,
  hostId,
  closeModals,
  mutation,
  formDescription,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();

  const form = useLinkForm({
    mode: 'uncontrolled',

    initialValues: {
      direction: undefined,
      underlying_communication_service_ids: undefined,
      band_id: undefined,
      type: undefined,
    },

    initialDirty: {
      direction: true,
      underlying_communication_service_ids: true,
      band_id: true,
      type: true,
    },

    transformValues: (values) => ({
      direction: values.direction === '' ? null : values.direction,
      underlying_communication_service_ids:
        values.underlying_communication_service_ids,
      link_rf:
        values.type === 'rf'
          ? { band_id: values.band_id === '' ? null : values.band_id }
          : null,
    }),

    validate: {
      // TODO: backend doesn't restrict how many IDs you can send as of v0.3.0.
      // When it does; should probably refactor this value.
      // Actually, you probably don't even need this since MultiSelect has a
      // maxValues prop.
      underlying_communication_service_ids: hasLength({ max: 20 }),
    },
  });

  if (!initializedFormValues.current) {
    form.setValues({
      direction: initialLink?.direction ?? '',
      underlying_communication_service_ids:
        initialLink?.underlying_communication_services?.map(
          (s) => s.underlying_communication_service_id,
        ) ?? [],
      band_id: initialLink?.link_rf?.band?.band_id ?? '',
      type: initialLink?.link_rf ? 'rf' : 'null',
    });
    initializedFormValues.current = true;
  }

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          let errMsg = '';
          if (error.detail.includes('Host ID')) {
            // When someone is on host's details page and opens create link form
            // and host is deleted.
            errMsg = `Host ID ${hostId} does not exist. The host has likely
              been deleted. Refresh the page.`;
            queryClient.invalidateQueries({ queryKey: ['hosts', hostId] });
          } else if (error.detail.includes('Link ID')) {
            // When someone is on host's details page and opens update link form
            // and link is deleted.
            errMsg = `Link ID ${initialLink.link_id} does not exist. The link
              has likely been deleted. Refresh the table.`;
            queryClient.invalidateQueries({
              queryKey: ['links', initialLink.link_id],
            });
          } else if (
            error.detail.includes('underlying_communication_service')
          ) {
            // FetchMultiSelect has outdated values for underlying comm services
            queryClient.invalidateQueries({
              queryKey: ['underlying-communication-services'],
            });
            form.setFieldValue(
              'underlying_communication_service_ids',
              Array.from(
                new Set(values.underlying_communication_service_ids).difference(
                  new Set(error.extra),
                ),
              ),
            );
            errMsg = `The following Underlying Communication Service IDs do not
              exist: ${error.extra.join(', ')}.
              Records have likely been deleted; refresh the form.`;
          } else if (error.detail.includes('Band ID')) {
            // FetchSelect has outdated values for bands
            form.setFieldValue('band_id', null);
            queryClient.invalidateQueries({ queryKey: ['bands'] });
            errMsg = `${error.detail}. Records have likely been deleted;
              refresh the form`;
          }
          setErrorSection(errMsg);
          scrollToErrorSection();
        } else if (error.status === 400) {
          switch (true) {
            case error.title.includes('Validation Error'):
              // TODO: This doesn't catch errors for link_rf.band_id because
              // our band_id is not nested.
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
    <Box maw={500} mx="auto">
      <Text c="dimmed" size="sm">
        {formDescription}
      </Text>
      <Space h="md" />
      <FormProvider form={form}>
        <form
          onSubmit={form.onSubmit(
            (values) => handleSubmit(form, values),
            (errors) => {
              const firstErrorPath = Object.keys(errors)[0];
              scrollElementIntoView(form.getInputNode(firstErrorPath));
            },
          )}
        >
          <Select
            label="Direction"
            placeholder="Direction"
            data={[
              'Full-duplex',
              'Half-duplex',
              'Simplex (incoming)',
              'Simplex (outgoing)',
            ]}
            {...form.getInputProps('direction')}
            key={form.key('direction')}
          />
          <FetchMultiSelect
            label="Underlying communication services"
            placeholder="Select underlying communication services"
            queryKey={['underlying-communication-services']}
            url={`/api/underlying-communication-services`}
            initialValue={initialLink?.underlying_communication_services}
            handleFormat={formatUnderlyingCommService}
            mt="sm"
            maxValues={20}
            {...form.getInputProps('underlying_communication_service_ids')}
            key={form.key('underlying_communication_service_ids')}
          />
          <Radio.Group
            name="type"
            label="Link type"
            mt="sm"
            {...form.getInputProps('type')}
            key={form.key('type')}
          >
            <Stack gap="xs">
              <Radio value="null" label="Null" />
              <Radio value="rf" label="Radio" />
            </Stack>
          </Radio.Group>
          <LinkRfField initialLink={initialLink} />
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
      </FormProvider>
    </Box>
  );
}
