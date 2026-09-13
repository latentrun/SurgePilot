export type CopyTextResult =
  | { ok: true }
  | { ok: false; reason: string };

const CLIPBOARD_UNAVAILABLE_MESSAGE =
  "Clipboard copy is unavailable. Use HTTPS or localhost, allow clipboard access, or select the text and copy it manually.";

const TEXT_PLAIN_MIME_TYPE = "text/plain";

function copyTextWithCopyEvent(text: string): boolean {
  if (typeof document.execCommand !== "function") {
    return false;
  }

  let clipboardDataWritten = false;

  const handleCopy = (event: ClipboardEvent) => {
    try {
      event.clipboardData?.setData(TEXT_PLAIN_MIME_TYPE, text);
      clipboardDataWritten = event.clipboardData != null;
      event.preventDefault();
    } catch {
      clipboardDataWritten = false;
    }
  };

  document.addEventListener("copy", handleCopy);
  try {
    document.execCommand("copy");
    return clipboardDataWritten;
  } catch {
    return false;
  } finally {
    document.removeEventListener("copy", handleCopy);
  }
}

export async function copyText(text: string): Promise<CopyTextResult> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return { ok: true };
    } catch {
      // Fall back to the legacy copy event path below. This keeps copy actions
      // usable on HTTP IP-based development deployments and older browsers.
    }
  }

  if (copyTextWithCopyEvent(text)) {
    return { ok: true };
  }

  return { ok: false, reason: CLIPBOARD_UNAVAILABLE_MESSAGE };
}
