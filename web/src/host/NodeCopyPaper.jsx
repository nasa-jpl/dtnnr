import { Anchor, Checkbox, Fieldset, NumberInput, Paper } from '@mantine/core';
import { useUncontrolled } from '@mantine/hooks';
import { Link } from '@tanstack/react-router';
import { memo } from 'react';
import FetchSelect from '../components/FetchSelect';
import { formatAllocator, formatOperator } from '../utils/formatFunctions';

export const NodeCopyPaper = memo(function NodeCopyPaper({
  form,
  node_id,
  allocator_id,
  node_number,
  index,
}) {
  let checkedInputProps = form.getInputProps(`nodes.${index}.active`, {
    type: `checkbox`,
  });
  const [_checkedValue, handleChange] = useUncontrolled({
    defaultValue: checkedInputProps.defaultChecked,
    onChange: checkedInputProps.onChange,
  });
  return (
    <Paper p="md" my="md" shadow="xs" withBorder>
      <Checkbox
        label={
          <>
            Node ID {node_id}{' '}
            <Anchor
              component={Link}
              to={`/nodes/${node_id}`}
              target="_blank"
              inherit
            >
              ({allocator_id}, {node_number})
            </Anchor>
          </>
        }
        defaultChecked={_checkedValue}
        onChange={() => handleChange(!_checkedValue)}
        key={form.key(`nodes.${index}.active`)}
      />
      {_checkedValue && (
        <>
          <Fieldset legend="Fully-qualified node number (FQNN)" mt="sm">
            <FetchSelect
              label="Allocator ID"
              placeholder="Allocator ID"
              queryKey={['allocators']}
              url={`/api/allocators`}
              initialValue={{
                allocator_id: '0',
                allocator_name: 'Default Allocator',
              }}
              handleFormat={formatAllocator}
              {...form.getInputProps(`nodes.${index}.allocator_id`)}
              key={form.key(`nodes.${index}.allocator_id`)}
            />
            <NumberInput
              withAsterisk
              label="Node number"
              placeholder="Node number"
              allowNegative={false}
              allowDecimal={false}
              mt="sm"
              {...form.getInputProps(`nodes.${index}.node_number`)}
              key={form.key(`nodes.${index}.node_number`)}
            />
          </Fieldset>
          <FetchSelect
            label="Operator"
            description="If an operator is used, the server will match the allocator ID for you."
            placeholder="Null"
            queryKey={['operators']}
            url={`/api/operators`}
            initialValue={null}
            handleFormat={formatOperator}
            mt="sm"
            {...form.getInputProps(`nodes.${index}.operator_id`)}
            key={form.key(`nodes.${index}.operator_id`)}
          />
        </>
      )}
    </Paper>
  );
});
