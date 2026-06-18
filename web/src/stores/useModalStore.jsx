import { create } from 'zustand';

export const useModalStore = create((set) => ({
  opened: false,
  children: null,
  options: {},
  open: (children, options = {}) =>
    set({
      opened: true,
      children,
      options,
    }),
  // Don't clear children in close() since Modal will re-render
  // during close transition.
  close: () => set({ opened: false }),
  clear: () => set({ children: null, options: {} }),
}));
