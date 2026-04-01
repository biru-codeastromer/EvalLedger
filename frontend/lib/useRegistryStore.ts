"use client";

import { create } from "zustand";

interface RegistryState {
  query: string;
  taskType: string;
  domains: string[];
  setQuery: (query: string) => void;
  setTaskType: (taskType: string) => void;
  toggleDomain: (domain: string) => void;
}

export const useRegistryStore = create<RegistryState>((set) => ({
  query: "",
  taskType: "",
  domains: [],
  setQuery: (query) => set({ query }),
  setTaskType: (taskType) => set({ taskType }),
  toggleDomain: (domain) =>
    set((state) => ({
      domains: state.domains.includes(domain)
        ? state.domains.filter((item) => item !== domain)
        : [...state.domains, domain]
    }))
}));

