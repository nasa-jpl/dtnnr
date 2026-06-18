import { Anchor } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { EntityTable } from '../components/EntityTable';
import { formatTelURI } from '../utils/formatFunctions';
import { ContactCreate } from './ContactCreate';
import classes from './ContactTable.module.css';

export function ContactTable({
  allocatorId,
  operatorId,
  hostId,
  nodeId,
  query,
  dissociateMutationToUse,
  dissociateMutationArgs = [],
  associateMutationToUse,
  associateMutationArgs = [],
}) {
  // useQuery here instead of in the parent so GET requests for contacts aren't
  // sent when the parent is 404
  const result = useQuery(query);
  // It isn't necessary to do useMutation here - we can do it in the parent entity
  // component - since the components to re-render with loading aren't inside a
  // modal created by the modals manager. But I do this anyway to be consistent with
  // how the other components that use EntityTable set up the `deleteRecord` prop.
  const dissociateMutation = dissociateMutationToUse(...dissociateMutationArgs);
  return (
    <EntityTable
      result={result}
      deleteRecord={dissociateMutation}
      deleteVerb="dissociate"
      fieldIdName="contact_id"
      columnsToShow={[
        {
          accessor: 'contact_id',
          title: 'ID',
          render: ({ contact_id }) => (
            <Anchor component={Link} size="sm" to={`/contacts/${contact_id}`}>
              {contact_id}
            </Anchor>
          ),
          noWrap: true,
        },
        {
          accessor: 'contact_name',
          title: 'Name',
          render: ({ contact_id, contact_name }) => (
            <div className={`${classes.tdCol} ${classes.name}`}>
              <Anchor component={Link} size="sm" to={`/contacts/${contact_id}`}>
                {contact_name}
              </Anchor>
            </div>
          ),
          width: '30%',
        },
        {
          accessor: 'email',
          title: 'Email',
          render: ({ email }) => (
            <div className={`${classes.tdCol} ${classes.email}`}>
              <Anchor size="sm" href={`mailto:${email}`}>
                {email}
              </Anchor>
            </div>
          ),
          width: '35%',
        },
        {
          accessor: 'primary_phone_number',
          title: 'Phone number (primary)',
          render: ({ primary_phone_number }) => (
            <div className={`${classes.tdCol} ${classes.phoneNumbers}`}>
              <Anchor size="sm" href={formatTelURI(primary_phone_number)}>
                {primary_phone_number}
              </Anchor>
            </div>
          ),
          width: '20%',
        },
      ]}
      createRecordName="Associate point of contact"
      handleCreateRecordModal={(closeModals) => (
        <ContactCreate
          allocatorId={allocatorId}
          operatorId={operatorId}
          hostId={hostId}
          nodeId={nodeId}
          mutationToUse={associateMutationToUse}
          mutationArgs={associateMutationArgs}
          closeModals={closeModals}
        />
      )}
    />
  );
}
