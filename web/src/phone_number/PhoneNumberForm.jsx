import {
  ActionIcon,
  Box,
  Button,
  Checkbox,
  Group,
  Space,
  Text,
} from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useLayoutEffect, useRef, useState } from 'react';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError } from '../utils/formatFunctions';
import { MAX_PHONE_NUMBERS } from '../utils/queries';
import { scrollElementIntoView, scrollToErrorSection } from '../utils/util';
import { PhoneInput } from './PhoneInput';
import classes from './PhoneNumberForm.module.css';

export function PhoneNumberForm({
  contactId,
  initialPhoneNumbers,
  closeModals,
  mutation,
}) {
  const initializedFormValues = useRef(false);
  const [errorSection, setErrorSection] = useState('');
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      phone_numbers: undefined,
    },

    initialDirty: {
      phone_numbers: true,
    },

    validate: {
      phone_numbers: {
        phone_number: isNotEmpty('Phone number may not be blank'),
      },
    },
  });

  useLayoutEffect(() => {
    if (!initializedFormValues.current) {
      if (!initialPhoneNumbers) {
        form.setValues({
          phone_numbers: [
            {
              phone_number: '',
              preferred: false,
              id: crypto.randomUUID(),
            },
          ],
        });
      } else {
        form.setValues({ phone_numbers: initialPhoneNumbers });
      }
      initializedFormValues.current = true;
    }
  }, [initialPhoneNumbers, form]);

  async function handleSubmit(_form, values) {
    mutation.mutate(values.phone_numbers.slice(0, MAX_PHONE_NUMBERS), {
      onSuccess: () => closeModals(),
      onError: (error) => {
        if (error.status === 404) {
          if (error.detail.includes('Contact ID')) {
            // For creating, the contact was deleted
            setErrorSection(
              `${error.detail}. Point of contact was deleted, refresh the page.`,
            );
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
          scrollToErrorSection();
        } else if (error.status === 400) {
          // Kinda sucks because API doesn't tell you at which index the error
          // happens, but empty phone numbers should be checked by our
          // validation function anyway.
          if (error.detail.includes('cannot consist solely of whitespace')) {
            setErrorSection(`${error.detail}.`);
          } else {
            // Shouldn't happen
            setErrorSection(error?.detail);
          }
          scrollToErrorSection();
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
        Use this form to replace the phone numbers of the point of contact
        identified by contact ID {contactId}. The first phone number is
        considered the contact's primary phone number.
      </Text>
      <Space h="md" />
      <form
        onSubmit={form.onSubmit(
          (values) => handleSubmit(form, values),
          (errors) => {
            const firstErrorPath = Object.keys(errors)[0];
            // can only be phone_number
            scrollElementIntoView(form.getInputNode(firstErrorPath));
          },
        )}
      >
        {(form.getValues().phone_numbers ?? []).map((pn, index) => (
          <div key={pn.id} className={classes.gridWrapper}>
            <PhoneInput
              label="Phone"
              placeholder="Phone"
              {...form.getInputProps(`phone_numbers.${index}.phone_number`)}
              key={form.key(`phone_numbers.${index}.phone_number`)}
            />
            <Checkbox
              label="Preferred"
              className={classes.preferredButton}
              {...form.getInputProps(`phone_numbers.${index}.preferred`, {
                type: 'checkbox',
              })}
              key={form.key(`phone_numbers.${index}.preferred`)}
            />
            <ActionIcon
              variant="subtle"
              color="red"
              className={classes.deleteButton}
              onClick={() => form.removeListItem('phone_numbers', index)}
            >
              <IconTrash className="icon-16-px" />
            </ActionIcon>
          </div>
        ))}
        <Button
          type="button"
          variant="light"
          fullWidth
          leftSection={<IconPlus className="icon-14-px" />}
          onClick={() => {
            form.insertListItem('phone_numbers', {
              phone_number: '',
              preferred: false,
              id: crypto.randomUUID(),
            });
          }}
        >
          Add phone number
        </Button>
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
