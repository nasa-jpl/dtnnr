import { ActionIcon, Button, Group, Menu, rem } from '@mantine/core';
import { IconChevronDown, IconPlus } from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';

export function NewButton({ children, ...otherProps }) {
  // TODO: consider modifying this to be a button menu which lets you
  // choose which entity (allocator / operator / host / node) to create.
  // See https://ui.mantine.dev/category/buttons/#button-menu
  // This is useful on larger screens, but on smaller screens it can be
  // obnoxious (the tabs bar is right above this button and the menu
  // items are harder to press than this button + extra clicks).
  // You could use a media query to show a regular button when viewport is
  // small, and the menu button when viewport is large, but now you have
  // the strange situation where rotating your device can change how this
  // button works.

  // let menuButton = (
  //   <Menu shadow="md" width={200}>
  //     <Menu.Target>
  //       <Button
  //         rightSection={
  //           <IconChevronDown className="icon-18-px" stroke={1.5} />
  //         }
  //         pr={12}
  //       >
  //         New
  //       </Button>
  //     </Menu.Target>
  //     <Menu.Dropdown>
  //       <Menu.Item component={Link} to="/allocators/create">
  //         Allocator
  //       </Menu.Item>
  //       <Menu.Item component={Link} to="/operators/create">
  //         Operator
  //       </Menu.Item>
  //       <Menu.Item component={Link} to="/hosts/create">
  //         Host
  //       </Menu.Item>
  //       <Menu.Item component={Link} to="/nodes/create">
  //         Node
  //       </Menu.Item>
  //     </Menu.Dropdown>
  //   </Menu>
  // );
  // let comboButton = (
  //   <Group wrap="nowrap" gap={0}>
  //     <Button
  //       style={{
  //         borderTopRightRadius: 0,
  //         borderBottomRightRadius: 0,
  //       }}
  //       component={Link}
  //       to="/allocators/create"
  //     >
  //       New allocator
  //     </Button>
  //     <Menu shadow="md" width={200}>
  //       <Menu.Target>
  //         <ActionIcon
  //           variant="filled"
  //           style={{
  //             borderTopLeftRadius: 0,
  //             borderBottomLeftRadius: 0,
  //             border: 0,
  //             borderLeft: 'calc(.0625rem * var(--mantine-scale)) solid var(--mantine-color-body)',
  //             height: rem(36),
  //             width: rem(36)
  //           }}
  //         >
  //           <IconChevronDown size={18} stroke={1.5} />
  //         </ActionIcon>
  //       </Menu.Target>
  //       <Menu.Dropdown>
  //         <Menu.Item component={Link} to="/operators/create">
  //           New operator
  //         </Menu.Item>
  //         <Menu.Item component={Link} to="/hosts/create">
  //           New host
  //         </Menu.Item>
  //         <Menu.Item component={Link} to="/nodes/create">
  //           New node
  //         </Menu.Item>
  //       </Menu.Dropdown>
  //     </Menu>
  //   </Group>
  // );

  return (
    <Button leftSection={<IconPlus className="icon-14-px" />} {...otherProps}>
      {children}
    </Button>
  );
}
