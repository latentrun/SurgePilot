import type { ApiError, LoadNodeStatus } from "../../../app/api-client";

export const statusCopy: Record<LoadNodeStatus, string> = {
  uninitialized: "Uninitialized",
  initializing: "Initializing",
  idle: "Idle",
  busy: "Running",
  offline: "Offline",
  quarantined: "Quarantined",
  disabled: "Disabled",
};

export function loadNodeErrorMessage(error: unknown) {
  const code = (error as ApiError | undefined)?.body?.code;
  switch (code) {
    case "LOAD_NODE_PUBLIC_ADMIN_REQUIRED":
      return "Only administrators can manage public load nodes.";
    case "LOAD_NODE_CONFLICT":
      return "A load node with the same host, port, and SSH user already exists.";
    case "LOAD_NODE_BUSY":
      return "This load node is currently running a job. Try again after it becomes idle.";
    case "LOAD_NODE_ACTION_NOT_ALLOWED":
      return "This action is not available for the current node status.";
    case "LOAD_NODE_CREDENTIAL_REQUIRED":
      return "Enter the required SSH credentials.";
    case "LOAD_NODE_CREDENTIAL_INVALID":
      return "The SSH credential format is invalid.";
    case "CREDENTIAL_DECRYPT_FAILED":
      return "Load Node credential encryption is unavailable. Ask an administrator to verify SSH_CREDENTIAL_ENCRYPTION_KEY and the stored credential data, then restart SurgePilot.";
    case "LOAD_NODE_HOST_INVALID":
      return "Enter a valid host name or IP address.";
    case "LOAD_NODE_RUNNER_HOME_INVALID":
      return "Enter a safe absolute path for Runner home.";
    case "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED":
      return "SurgePilot could not scan the SSH host key. Check the host, port, and network path.";
    case "LOAD_NODE_SSH_HOST_KEY_MISMATCH":
      return "The SSH host key changed after scanning. Scan the host again before saving.";
    case "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED":
      return "Scan and confirm the SSH host key before initializing this load node.";
    case "LOAD_NODE_SSH_HOST_KEY_CHANGED":
      return "The SSH host key no longer matches the trusted key. Review the host before using this node.";
    case "WORKSPACE_ACCESS_DENIED":
      return "You do not have access to this workspace.";
    case "RESOURCE_NOT_FOUND":
      return "The load node does not exist or is no longer visible.";
    case "VALIDATION_ERROR":
      return "Check the highlighted fields and try again.";
    default:
      return "The operation failed. Please try again.";
  }
}
