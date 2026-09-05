import {
  createContext,
  useContext,
  useEffect,
  type ReactNode,
} from "react";

export type WorkspaceSwitchGuard = {
  dirty: boolean;
  onAbandon?: () => void;
  safePath: string;
};

const WorkspaceSwitchGuardContext = createContext<
  ((guard: WorkspaceSwitchGuard | null) => void) | null
>(null);

export function WorkspaceSwitchGuardProvider({
  children,
  onGuardChange,
}: Readonly<{
  children: ReactNode;
  onGuardChange: (guard: WorkspaceSwitchGuard | null) => void;
}>) {
  return (
    <WorkspaceSwitchGuardContext.Provider value={onGuardChange}>
      {children}
    </WorkspaceSwitchGuardContext.Provider>
  );
}

export function useWorkspaceSwitchGuard(guard: WorkspaceSwitchGuard | null) {
  const onGuardChange = useContext(WorkspaceSwitchGuardContext);

  useEffect(() => {
    if (!onGuardChange) {
      return undefined;
    }
    onGuardChange(guard);
    return () => onGuardChange(null);
  }, [guard, onGuardChange]);
}
