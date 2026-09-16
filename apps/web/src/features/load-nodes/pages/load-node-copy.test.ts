import { describe, expect, it } from "vitest";

import { ApiError } from "../../../app/api-client";
import { loadNodeErrorMessage } from "./load-node-copy";

describe("loadNodeErrorMessage", () => {
  it("explains how to recover when credential encryption is not configured", () => {
    const error = new ApiError(500, {
      code: "CREDENTIAL_DECRYPT_FAILED",
      message: "Credential encryption is not configured.",
      requestId: "request-id",
    });

    expect(loadNodeErrorMessage(error)).toBe(
      "Load Node credential encryption is unavailable. Ask an administrator to verify SSH_CREDENTIAL_ENCRYPTION_KEY and the stored credential data, then restart SurgePilot.",
    );
  });
});
