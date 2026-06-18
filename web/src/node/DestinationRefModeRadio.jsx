import { Group, Radio, Stack, Text } from '@mantine/core';
import classes from './DestinationRefModeRadio.module.css';

export function DestinationRefModeRadio({
  options,
  destRefModeRadioDisabled,
  form,
}) {
  const destination_ref_mode_cards = options.map((item) => (
    <Radio.Card
      disabled={destRefModeRadioDisabled}
      className={classes.root}
      radius="md"
      value={item.name}
      key={item.name}
    >
      <Group wrap="nowrap" align="flex-start">
        <Radio.Indicator disabled={destRefModeRadioDisabled} />
        <div>
          <Text className={classes.label}>{item.name}</Text>
          <Text className={classes.description}>{item.description}</Text>
        </div>
      </Group>
    </Radio.Card>
  ));
  return (
    <Radio.Group
      label="Destination reference mode"
      description="Control what happens to destinations of inducts and seats"
      mt="sm"
      {...form.getInputProps('destination_ref_mode')}
      key={form.key('destination_ref_mode')}
    >
      <Stack pt="md" gap="xs">
        {destination_ref_mode_cards}
      </Stack>
    </Radio.Group>
  );
}
