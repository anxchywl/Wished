import { create } from "zustand";

type AppState = {
  isBootstrapped: boolean;
  setBootstrapped: (value: boolean) => void;
};

export const useAppStore = create<AppState>((set) => ({
  isBootstrapped: false,
  setBootstrapped: (value) => set({ isBootstrapped: value }),
}));
