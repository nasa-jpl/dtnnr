import { Modal } from '@mantine/core';
import { useModalStore } from '../stores/useModalStore';
import { useIsMobile } from '../utils/util';

export function GlobalModal() {
  const { opened, children, options, close, clear } = useModalStore();
  const isMobile = useIsMobile();

  return (
    <Modal
      centered
      transitionProps={isMobile && { transition: 'fade', duration: 200 }}
      {...options}
      opened={opened}
      onClose={close}
      onExitTransitionEnd={clear}
      fullScreen={options.fullScreen ?? isMobile}
    >
      {children}
    </Modal>
  );
}
