import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
};

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs() {
  const context = useContext(TabsContext);
  if (!context) throw new Error("Tabs components must be used inside Tabs");
  return context;
}

export function Tabs({
  children,
  className,
  defaultValue,
}: {
  children: ReactNode;
  className?: string;
  defaultValue: string;
}) {
  const [value, setValue] = useState(defaultValue);
  return (
    <TabsContext.Provider value={{ value, setValue }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  "aria-label": ariaLabel,
  children,
}: {
  "aria-label"?: string;
  children: ReactNode;
}) {
  return (
    <div aria-label={ariaLabel} className="flex w-full min-w-max gap-1 border-b border-white/10" role="tablist">
      {children}
    </div>
  );
}

export function TabsTrigger({ children, value }: { children: ReactNode; value: string }) {
  const tabs = useTabs();
  const active = tabs.value === value;
  return (
    <button
      aria-selected={active}
      className={`relative whitespace-nowrap px-4 py-3 text-sm font-semibold outline-none transition hover:text-white focus-visible:ring-2 focus-visible:ring-primary/60 ${active ? "text-white after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-primary" : "text-text-muted"}`}
      onClick={() => tabs.setValue(value)}
      role="tab"
      type="button"
    >
      {children}
    </button>
  );
}

export function TabsContent({ children, value }: { children: ReactNode; value: string }) {
  const tabs = useTabs();
  if (tabs.value !== value) return null;
  return <div role="tabpanel">{children}</div>;
}
