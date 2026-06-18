import { Anchor, Badge, Button, Loader } from '@mantine/core';
import { IconEdit } from '@tabler/icons-react';
import { ErrorComponent } from '@tanstack/react-router';
import entityTableClasses from '../components/EntityTable.module.css';
import { useModalStore } from '../stores/useModalStore';
import { formatTelURI } from '../utils/formatFunctions';
import {
  usePhoneNumberAllQuery,
  useReplacePhoneNumberMutation,
} from '../utils/queries';
import { PhoneNumberForm } from './PhoneNumberForm';
import classes from './PhoneNumberList.module.css';

export function PhoneNumberList({ contactId }) {
  const { isPending, isError, data, error } = usePhoneNumberAllQuery(contactId);
  const replacePhoneNumberMutation = useReplacePhoneNumberMutation(contactId);
  const openModal = useModalStore((s) => s.open);
  const closeModal = useModalStore((s) => s.close);

  if (isPending) {
    return <Loader />;
  } else if (isError) {
    return <ErrorComponent error={error} />;
  }

  return (
    <>
      {data.items.map((pn) => (
        <div key={pn.id} className={classes.itemContainer}>
          <span className={classes.phoneNumberText}>
            <Anchor href={formatTelURI(pn.phone_number)}>
              {pn.phone_number}
            </Anchor>
          </span>
          <span className={classes.preferredText}>
            {pn.preferred && (
              <Badge mx="sm" variant="dot">
                Preferred
              </Badge>
            )}
          </span>
        </div>
      ))}
      <div className={entityTableClasses.buttonsWrapper}>
        <Button
          mt="sm"
          className={entityTableClasses.createButton}
          leftSection={<IconEdit className="icon-14-px" />}
          onClick={() =>
            openModal(
              <PhoneNumberForm
                contactId={contactId}
                initialPhoneNumbers={data.items}
                closeModals={closeModal}
                mutation={replacePhoneNumberMutation}
              />,
              { title: 'Edit phone numbers' },
            )
          }
        >
          Edit phone numbers
        </Button>
      </div>
    </>
  );
}
