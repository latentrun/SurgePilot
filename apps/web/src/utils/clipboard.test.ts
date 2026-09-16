import { afterEach, describe, expect, it, vi } from "vitest";

import { copyText } from "./clipboard";

const UNAVAILABLE_MESSAGE =
  "Clipboard copy is unavailable. Use HTTPS or localhost, allow clipboard access, or select the text and copy it manually.";

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", {
    configurable: true,
    value,
  });
}

function setClipboard(writeText?: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  });
}

function setExecCommand(value: (command: string) => boolean) {
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value,
  });
}

function createCopyEvent(setData: (type: string, data: string) => void) {
  const event = new Event("copy", {
    bubbles: true,
    cancelable: true,
  }) as ClipboardEvent;

  Object.defineProperty(event, "clipboardData", {
    configurable: true,
    value: { setData },
  });

  return event;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("copyText", () => {
  it("uses the Clipboard API in secure contexts", async () => {
    setSecureContext(true);
    const writeText = vi.fn(() => Promise.resolve());
    setClipboard(writeText);
    const execCommand = vi.fn(() => false);
    setExecCommand(execCommand);

    await expect(copyText("copy me")).resolves.toEqual({ ok: true });

    expect(writeText).toHaveBeenCalledWith("copy me");
    expect(execCommand).not.toHaveBeenCalled();
  });

  it("falls back to a copy event outside secure contexts", async () => {
    setSecureContext(false);
    setClipboard(undefined);
    const setData = vi.fn();
    const execCommand = vi.fn((command: string) => {
      expect(command).toBe("copy");
      document.dispatchEvent(createCopyEvent(setData));
      return false;
    });
    setExecCommand(execCommand);

    await expect(copyText("legacy copy")).resolves.toEqual({ ok: true });

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(setData).toHaveBeenCalledWith("text/plain", "legacy copy");
  });

  it("falls back when Clipboard API rejects", async () => {
    setSecureContext(true);
    const writeText = vi.fn(() => Promise.reject(new Error("denied")));
    setClipboard(writeText);
    const setData = vi.fn();
    setExecCommand(() => {
      document.dispatchEvent(createCopyEvent(setData));
      return true;
    });

    await expect(copyText("copy me")).resolves.toEqual({ ok: true });

    expect(writeText).toHaveBeenCalledWith("copy me");
    expect(setData).toHaveBeenCalledWith("text/plain", "copy me");
  });

  it("returns a clear failure reason when fallback does not write clipboard data", async () => {
    setSecureContext(false);
    setClipboard(undefined);
    const execCommand = vi.fn(() => true);
    setExecCommand(execCommand);

    await expect(copyText("legacy copy")).resolves.toEqual({
      ok: false,
      reason: UNAVAILABLE_MESSAGE,
    });

    expect(execCommand).toHaveBeenCalledWith("copy");
  });
});
