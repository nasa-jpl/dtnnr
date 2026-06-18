import { Button, NumberInput, Select, Space } from '@mantine/core';
import { isNotEmpty, useForm } from '@mantine/form';
import { IconArrowRight } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FormErrorSection } from '../components/FormErrorSection';
import { LoginError } from '../components/LoginError';
import { formatGeneralError } from '../utils/formatFunctions';
import { useUpdateAllocatedNodeNumbersMutation } from '../utils/queries';
import {
  scrollElementIntoView,
  scrollToErrorSection,
  setAndScrollForExtra,
} from '../utils/util';
import classes from './AllocatedNodeNumbersUpdate.module.css';

export function AllocatedNodeNumbersUpdate({ operatorId }) {
  const [errorSection, setErrorSection] = useState('');
  const queryClient = useQueryClient();
  const mutation = useUpdateAllocatedNodeNumbersMutation(operatorId);
  const form = useForm({
    mode: 'uncontrolled',

    initialValues: {
      operation: 'Union',
      bounds: '[]',
      lower: '',
      upper: '',
    },

    transformValues: (values) => ({
      ...values,
      operation: values.operation.toLowerCase(),
      lower: values.lower !== '' ? values.lower : 0,
      upper: values.upper !== '' ? values.upper : 2 ** 32 - 1,
    }),

    validate: {
      operation: isNotEmpty('Operation cannot be null.'),
      lower: (value, values) =>
        value === ''
          ? null
          : Number(value) < 0 || Number(value) > 2 ** 32 - 1
            ? 'Must be between 0 and 2^32 - 1'
            : values.upper === ''
              ? null
              : Number(value) > Number(values.upper)
                ? 'Lower bound cannot be greater than upper bound'
                : null,
      upper: (value) =>
        value === ''
          ? null
          : Number(value) < 0 || Number(value) > 2 ** 32 - 1
            ? 'Must be between 0 and 2^32 - 1'
            : null,
      // The lower bound can't be greater than upper bound message is sufficient
      // so there's no need to say it again here
    },
  });

  async function handleSubmit(form, values) {
    mutation.mutate(values, {
      onError: (error) => {
        if (error.status === 400) {
          if (error.title.includes('Validation Error')) {
            setAndScrollForExtra(form, error.extra);
          } else {
            setErrorSection(error.detail);
            scrollToErrorSection();
          }
        } else if (error.status === 404) {
          queryClient.invalidateQueries({
            queryKey: ['operators', operatorId],
          });
          setErrorSection(
            error.detail +
              ' This operator has been deleted, refresh the page to update.',
          );
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
    <form
      onSubmit={form.onSubmit(
        (values) => handleSubmit(form, values),
        (errors) => {
          const firstErrorPath = Object.keys(errors)[0];
          scrollElementIntoView(
            form.getInputNode(firstErrorPath),
            firstErrorPath.includes('lower') ||
              firstErrorPath.includes('upper'),
          );
        },
      )}
    >
      <div className={classes.wrapper}>
        <div className={`${Select.classes.label} ${classes.opLabel}`}>
          Operation
        </div>
        <Select
          placeholder="Operation"
          data={['Union', 'Intersection', 'Difference']}
          allowDeselect={false}
          {...form.getInputProps('operation')}
          key={form.key('operation')}
          className={classes.op}
          classNames={{
            wrapper: classes.inputWrapper,
          }}
        />
        <div className={classes.boundsLabelDesc}>
          <div className={Select.classes.label}>Bounds</div>
          <div className={Select.classes.description}>
            If this is empty, bounds is []
          </div>
        </div>
        <Select
          placeholder="Bounds"
          data={['()', '[)', '(]', '[]']}
          {...form.getInputProps('bounds')}
          key={form.key('bounds')}
          className={classes.bounds}
          classNames={{
            wrapper: classes.inputWrapper,
          }}
        />
        <div className={classes.lowerLabelDesc}>
          <div className={NumberInput.classes.label}>Lower bound</div>
          <div className={NumberInput.classes.description}>
            If this is empty, lower bound is 0
          </div>
        </div>
        <NumberInput
          placeholder="Lower bound"
          allowNegative={false}
          allowDecimal={false}
          {...form.getInputProps('lower')}
          key={form.key('lower')}
          className={classes.lower}
          classNames={{
            wrapper: classes.inputWrapper,
          }}
        />
        <div className={classes.upperLabelDesc}>
          <div className={NumberInput.classes.label}>Upper bound</div>
          <div className={NumberInput.classes.description}>
            If this is empty, upper bound is 2^32 - 1
          </div>
        </div>
        <NumberInput
          placeholder="Upper bound"
          allowNegative={false}
          allowDecimal={false}
          {...form.getInputProps('upper')}
          key={form.key('upper')}
          className={classes.upper}
          classNames={{
            wrapper: classes.inputWrapper,
          }}
        />
        <Space h="md" hiddenFrom="xs" />
        <Button
          type="submit"
          rightSection={<IconArrowRight className="icon-14-px" />}
          loading={mutation.isPending}
          onClick={() => setErrorSection('')}
          className={classes.submit}
        >
          Update
        </Button>
        {/* Prevents content from being pushed when error appears. Use a line
          break because the error message wraps near breakpoint. */}
        <div className={`${classes.empty} ${NumberInput.classes.error}`}>
          &nbsp;
          <br />
          &nbsp;
        </div>
      </div>
      {errorSection !== '' && (
        <FormErrorSection
          message={errorSection}
          setErrorSection={setErrorSection}
        />
      )}
    </form>
  );
}
