import {
  ActionIcon,
  Button,
  Center,
  Group,
  rem,
  Space,
  Text,
} from '@mantine/core';
import {
  IconClick,
  IconEdit,
  IconPlus,
  IconTrash,
  IconX,
} from '@tabler/icons-react';
import { DataTable } from 'mantine-datatable';
import { useContext, useEffect, useState } from 'react';
import AuthContext from '../AuthContext';
import { useModalStore } from '../stores/useModalStore';
import { formatGeneralError } from '../utils/formatFunctions';
import { DangerConfirmModal } from './DangerConfirmModal';
import classes from './EntityTable.module.css';
import ErrorComponent from './ErrorComponent';
import { FormErrorSection } from './FormErrorSection';

const triggerConfirm = (
  openModal,
  closeModal,
  { record, onConfirm, fieldIdName, verb = 'delete' },
) => {
  const isBulk = Array.isArray(record);
  const verbUpper = verb.charAt(0).toUpperCase() + verb.slice(1);

  openModal(
    <DangerConfirmModal
      description={
        <Text size="sm">
          Are you sure you want to{` `}
          {isBulk
            ? `${verb} the selected records`
            : `${verb} record ID ${record[fieldIdName]}`}
          ? This action is destructive and cannot be undone.
        </Text>
      }
      confirmMessage={`${verbUpper} record${isBulk ? 's' : ''}`}
      cancelMessage={`No don't ${verb}`}
      closeModals={closeModal}
      onConfirm={
        isBulk ? () => record.forEach(onConfirm) : () => onConfirm(record)
      }
    />,
    {
      title: `${verbUpper} ${isBulk ? 'selected' : 'record'}`,
    },
  );
};

/**
 * Actions rendered for each row of EntityTable
 * @param {object} record object associated with a row
 * @param {function} onEdit takes (record, openModal, closeModal)
 *   to open a modal
 * @param {function} onDeleteConfirm function to invoke on a record on delete
 * @param {string} deleteVerb word to render for delete form
 * @param {string} fieldIdName name of a record's ID field
 * @returns
 */
export function TableActions({
  record,
  onEdit,
  onDeleteConfirm,
  deleteVerb,
  fieldIdName,
}) {
  const openModal = useModalStore((s) => s.open);
  const closeModal = useModalStore((s) => s.close);

  return (
    <Group gap={4} justify="center" wrap="nowrap">
      {onEdit && (
        <ActionIcon
          size="md"
          variant="subtle"
          onClick={(e) => {
            e.stopPropagation();
            onEdit(record, openModal, closeModal);
          }}
        >
          <IconEdit className="icon-16-px" />
        </ActionIcon>
      )}

      {onDeleteConfirm && (
        <ActionIcon
          size="md"
          variant="subtle"
          color="red"
          onClick={(e) => {
            e.stopPropagation();
            triggerConfirm(openModal, closeModal, {
              record,
              onConfirm: onDeleteConfirm,
              fieldIdName,
              verb: deleteVerb,
            });
          }}
        >
          {deleteVerb === 'dissociate' ? (
            <IconX className="icon-16-px" />
          ) : (
            <IconTrash className="icon-16-px" />
          )}
        </ActionIcon>
      )}
    </Group>
  );
}

/**
 * General entity table for displaying information about related entities of the
 * main entities.
 * @param {object} result value returned from calling useQuery()
 * @param {function} processResultData function called before using result.data
 * @param {object} deleteRecord value returned from calling useMutation()
 * @param {string} deleteVerb word to render for "delete" components
 *   to render icons and descriptions differently
 * @param {string} fieldIdName name of a record's ID field
 * @param {string} initialColumnAccessor initial column to sort by, fieldIdName by default
 * @param {string} initialSortDirection initial sort direction
 * @param {function} descSortedDataFunction handles how desecending data should look given sorted array
 * @param {Array} columnsToShow Mantine DataTabel column properties
 * @param {function} rowExpansionContent given a record, returns component that displays more details
 * @param {string} createRecordName label of the create record button / title of create record modal
 * @param {function} handleCreateRecordModal returns form for inserting records
 * @param {function} onEdit given (record, openModal, closeModal) to open a modal with a form
 * @param {function} renderActions if set, takes
 *   (record, openModal, closeModal, deleteRecordMutate) to render
 *   a custom actions column
 * @returns {object} the table
 */
export function EntityTable({
  result,
  processResultData = (x) => x,
  deleteRecord,
  deleteVerb = 'delete',
  fieldIdName,
  initialColumnAccessor = fieldIdName,
  initialSortDirection = 'asc',
  descSortedDataFunction = (arr, _columnAccessor) => arr.reverse(),
  columnsToShow,
  rowExpansionContent,
  createRecordName,
  handleCreateRecordModal,
  onEdit,
  renderActions,
  ...props
}) {
  const { currentUser } = useContext(AuthContext);
  const [records, setRecords] = useState([]);
  const [selectedRecords, setSelectedRecords] = useState([]);
  const [tableError, setTableError] = useState('');
  const openModal = useModalStore((s) => s.open);
  const closeModal = useModalStore((s) => s.close);

  // biome-ignore lint/correctness/useExhaustiveDependencies: suggestion breaks
  useEffect(() => {
    if (!result.data) {
      setSelectedRecords([]);
      return;
    }
    let processedData = processResultData(result.data).items.concat();
    setRecords(processedData);
  }, [result]);

  const deleteVerbUpper =
    deleteVerb.charAt(0).toUpperCase() + deleteVerb.slice(1);

  if (result.isError) {
    // At the moment, components don't render EntityTable when the backend
    // is down, so this shouldn't matter anyway
    return <ErrorComponent error={result.error} />;
  }

  if (
    selectedRecords.length !==
    selectedRecords.filter((o1) =>
      processResultData(result.data).items.some(
        (o2) => o1[fieldIdName] === o2[fieldIdName],
      ),
    ).length
  ) {
    setSelectedRecords(
      selectedRecords.filter((o1) =>
        processResultData(result.data).items.some(
          (o2) => o1[fieldIdName] === o2[fieldIdName],
        ),
      ),
    );
  }

  function deleteRecordMutate(record) {
    deleteRecord.mutate(record, {
      onSuccess: () => {
        let index = selectedRecords
          .map((e) => e[fieldIdName])
          .indexOf(record[fieldIdName]);
        if (index > -1) {
          setSelectedRecords(selectedRecords.toSpliced(index, 1));
        }
      },
      // TODO: remember onError when using .mutate() only applies to the very
      // last one https://tanstack.com/query/latest/docs/react/guides/mutations#consecutive-mutations
      // If we want to show all errors, we need to use useMutation directly,
      // but should we even show an error? Data refreshes frequently, if someone
      // deleted the data before we deleted it, is that an error?
      onError: (error) => {
        setTableError(
          tableError +
            `Failed to ${deleteWord} record id ${record[fieldIdName]}.` +
            ` ${formatGeneralError(error)}\r\n`,
        );
      },
    });
  }

  const renderColumnActions = (record) => {
    if (renderActions) {
      return renderActions(record, openModal, closeModal, deleteRecordMutate);
    }
    return (
      <TableActions
        record={record}
        onEdit={onEdit}
        onDeleteConfirm={deleteRecordMutate}
        deleteVerb={deleteVerb}
        fieldIdName={fieldIdName}
      />
    );
  };

  return (
    <div className="show-white-space">
      <DataTable
        minHeight={
          processResultData(result?.data)?.items?.length === 0
            ? rem(150)
            : false
        }
        striped
        highlightOnHover
        pinLastColumn={currentUser ?? false}
        withTableBorder
        withColumnBorders
        columns={
          currentUser
            ? columnsToShow.concat([
                {
                  accessor: 'actions',
                  title: (
                    <Center>
                      <IconClick className="icon-16-px" />
                    </Center>
                  ),
                  width: '0%',
                  render: renderColumnActions,
                },
              ])
            : columnsToShow
        }
        records={records}
        rowExpansion={
          rowExpansionContent === undefined
            ? false
            : {
                allowMultiple: true,
                content: ({ record }) => rowExpansionContent(record),
              }
        }
        fetching={result.isPending || deleteRecord.isPending}
        selectedRecords={selectedRecords}
        onSelectedRecordsChange={setSelectedRecords}
        idAccessor={fieldIdName}
        className="scale-table-icons"
        {...props}
      />
      {currentUser && (
        <>
          <Space h="md" />
          <div className={classes.buttonsWrapper}>
            {handleCreateRecordModal && (
              <Button
                leftSection={<IconPlus className="icon-14-px" />}
                onClick={() =>
                  openModal(handleCreateRecordModal(closeModal), {
                    title: createRecordName,
                  })
                }
                className={classes.createButton}
              >
                {createRecordName}
              </Button>
            )}
            {deleteRecord && (
              <Button
                disabled={selectedRecords.length < 1}
                leftSection={
                  deleteVerb === 'dissociate' ? (
                    <IconX className="icon-16-px" />
                  ) : (
                    <IconTrash className="icon-14-px" />
                  )
                }
                color="red"
                onClick={() => {
                  triggerConfirm(openModal, closeModal, {
                    record: selectedRecords,
                    onConfirm: deleteRecordMutate,
                    fieldIdName,
                    verb: deleteVerb,
                  });
                }}
                loading={deleteRecord.isPending}
                className={classes.deleteButton}
              >
                {selectedRecords.length === 0
                  ? `Select records to ${deleteVerb}`
                  : selectedRecords.length === 1
                    ? `${deleteVerbUpper} 1 selected record`
                    : `${deleteVerbUpper} ${selectedRecords.length} selected records`}
              </Button>
            )}
          </div>
        </>
      )}
      {tableError !== '' && (
        <FormErrorSection
          message={tableError}
          setErrorSection={setTableError}
        />
      )}
    </div>
  );
}
