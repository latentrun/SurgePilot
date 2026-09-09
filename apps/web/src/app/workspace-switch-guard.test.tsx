import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  WorkspaceSwitchGuardProvider,
  useWorkspaceSwitchGuard,
} from "./workspace-switch-guard";

describe("P1-03 workspace switch guard", () => {
  it("registers and clears a dirty editor guard", () => {
    const onGuardChange = vi.fn();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <WorkspaceSwitchGuardProvider onGuardChange={onGuardChange}>
        {children}
      </WorkspaceSwitchGuardProvider>
    );

    const { unmount } = renderHook(
      () => useWorkspaceSwitchGuard({ dirty: true, safePath: "/scenarios" }),
      { wrapper },
    );

    expect(onGuardChange).toHaveBeenLastCalledWith({
      dirty: true,
      safePath: "/scenarios",
    });
    unmount();
    expect(onGuardChange).toHaveBeenLastCalledWith(null);
  });
});
