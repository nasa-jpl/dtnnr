import { Space, Tabs } from '@mantine/core';
import { ContactForm } from './ContactForm';
import { ExistingContactForm } from './ExistingContactForm';

export function ContactCreate({
  allocatorId,
  operatorId,
  hostId,
  nodeId,
  closeModals,
  mutationToUse,
  mutationArgs = [],
}) {
  const mutation = mutationToUse(...mutationArgs);
  return (
    <Tabs defaultValue="existing">
      <Tabs.List>
        <Tabs.Tab value="existing">Existing</Tabs.Tab>
        <Tabs.Tab value="new">New</Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="existing">
        <Space h="md" />
        <ExistingContactForm
          allocatorId={allocatorId}
          operatorId={operatorId}
          hostId={hostId}
          nodeId={nodeId}
          closeModals={closeModals}
          mutation={mutation}
          formDescription={`Select a point of contact to associate with ${
            allocatorId !== undefined
              ? `allocator ID ${allocatorId}`
              : operatorId !== undefined
                ? `operator ID ${operatorId}`
                : hostId !== undefined
                  ? `host ID ${hostId}`
                  : `node ID ${nodeId}`
          }.`}
        />
      </Tabs.Panel>

      <Tabs.Panel value="new">
        <Space h="md" />
        <ContactForm
          allocatorId={allocatorId}
          operatorId={operatorId}
          hostId={hostId}
          nodeId={nodeId}
          closeModals={closeModals}
          mutation={mutation}
          formDescription={`Create a new point of contact to associate with ${
            allocatorId !== undefined
              ? `allocator ID ${allocatorId}`
              : operatorId !== undefined
                ? `operator ID ${operatorId}`
                : hostId !== undefined
                  ? `host ID ${hostId}`
                  : `node ID ${nodeId}`
          }.`}
        />
      </Tabs.Panel>
    </Tabs>
  );
}
