import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";

import {
  ApiError,
  createEnvGroup,
  deleteEnvGroup,
  duplicateEnvGroup,
  getCsrfToken,
  getEnvGroup,
  listEnvGroups,
  patchEnvGroup,
  type EnvGroupDetail,
  type EnvGroupSummary,
  type EnvGroupVariableRead,
  type EnvGroupVariableWrite,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { cn } from "../../../utils/cn";

type FormMode = "create" | "edit";
type VariableType = "plain" | "secret";
type VariableRow = {
  id: string;
  key: string;
  type: VariableType;
  value: string;
  hasExistingSecret?: boolean;
};

type FormState = {
  description: string;
  name: string;
  variables: VariableRow[];
};

const emptyForm: FormState = { description: "", name: "", variables: [] };
const keyPattern = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const pageSize = 20;
let fallbackClientIdSequence = 0;

function createClientId() {
  const randomUUID = globalThis.crypto?.randomUUID;
  if (typeof randomUUID === "function") {
    return randomUUID.call(globalThis.crypto);
  }
  fallbackClientIdSequence += 1;
  return `client-${Date.now()}-${fallbackClientIdSequence}`;
}

function emptyVariableRow(): VariableRow {
  return { id: createClientId(), key: "", type: "plain", value: "" };
}

function detailToForm(detail: EnvGroupDetail): FormState {
  return {
    name: detail.name,
    description: detail.description ?? "",
    variables: Object.entries(detail.variables ?? {}).map(([key, variable]) => {
      const typed = variable as EnvGroupVariableRead;
      if (typed.type === "secret") {
        return {
          id: createClientId(),
          key,
          type: "secret" as const,
          value: "",
          hasExistingSecret: typed.hasValue,
        };
      }
      return {
        id: createClientId(),
        key,
        type: "plain" as const,
        value: typed.value,
      };
    }),
  };
}

function variablesFromRows(
  rows: VariableRow[],
): Record<string, EnvGroupVariableWrite> {
  return Object.fromEntries(
    rows
      .filter((row) => row.key !== "")
      .map((row) => {
        if (row.type === "secret") {
          const entry: EnvGroupVariableWrite =
            row.hasExistingSecret && row.value === ""
              ? { type: "secret" }
              : { type: "secret", value: row.value };
          return [row.key, entry];
        }
        return [
          row.key,
          { type: "plain", value: row.value } satisfies EnvGroupVariableWrite,
        ];
      }),
  );
}

function formHasDraft(form: FormState) {
  return (
    form.name.trim() !== "" ||
    form.description.trim() !== "" ||
    form.variables.some(
      (row) => row.key !== "" || row.value !== "" || row.type !== "plain",
    )
  );
}

function variableKeyFromApiField(field: string) {
  if (field.startsWith("variables.")) {
    return field.slice("variables.".length);
  }
  const bracketMatch = /^variables\[(.*)]$/.exec(field);
  return bracketMatch?.[1] ?? null;
}

function mapApiValidationField(
  field: string,
  message: string,
  form: FormState,
) {
  const variableKey = variableKeyFromApiField(field);
  if (variableKey === null) {
    return field;
  }
  const row = form.variables.find((variable) => variable.key === variableKey);
  if (!row) {
    return field;
  }
  const target = message.toLowerCase().includes("value") ? "value" : "key";
  return `variables.${row.id}.${target}`;
}

function validateForm(form: FormState) {
  const errors: Record<string, string> = {};
  const name = form.name.trim();
  if (!name) {
    errors.name = "Name is required.";
  } else if (name.length > 120) {
    errors.name = "Name must be 120 characters or less.";
  }
  if (form.description.trim().length > 500) {
    errors.description = "Description must be 500 characters or less.";
  }

  const seen = new Set<string>();
  for (const row of form.variables) {
    if (!row.key) {
      errors[`variables.${row.id}.key`] = "Key is required.";
    } else if (!keyPattern.test(row.key)) {
      errors[`variables.${row.id}.key`] =
        "Use letters, numbers, and underscores; do not start with a number.";
    } else if (seen.has(row.key)) {
      errors[`variables.${row.id}.key`] = "Key must be unique.";
    } else {
      seen.add(row.key);
    }
    if (new TextEncoder().encode(row.value).length > 4096) {
      errors[`variables.${row.id}.value`] = "Value must be 4096 bytes or less.";
    }
  }
  if (form.variables.length > 200) {
    errors.variables = "A group can contain at most 200 variables.";
  }
  return errors;
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") {
      return "You do not have access to this workspace.";
    }
    if (error.body.code === "RESOURCE_NOT_FOUND") {
      return "The Env Group was not found.";
    }
    return "Something went wrong. Try again.";
  }
  return "Something went wrong. Try again.";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

export function EnvGroupsPage() {
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [q, setQ] = useState("");
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [formApiError, setFormApiError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<EnvGroupSummary | null>(
    null,
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const workspaceId = session?.defaultWorkspace.id ?? "";
  const listQueryKey = ["env-groups", workspaceId, q, page];
  const listQuery = useQuery({
    enabled: session !== null,
    queryKey: listQueryKey,
    queryFn: () =>
      listEnvGroups({ workspaceId, page, pageSize, q, sort: "-createdAt" }),
  });
  const detailQuery = useQuery({
    enabled: formOpen && formMode === "edit" && editingId !== null,
    queryKey: ["env-group", workspaceId, editingId],
    queryFn: () => getEnvGroup(editingId as string, workspaceId),
  });

  useEffect(() => {
    if (
      formOpen &&
      formMode === "edit" &&
      editingId !== null &&
      detailQuery.data
    ) {
      setForm(detailToForm(detailQuery.data));
      setFormErrors({});
      setFormApiError(null);
    }
  }, [detailQuery.data, editingId, formMode, formOpen]);

  const rows = listQuery.data?.items ?? [];
  const isEmpty =
    !listQuery.isLoading && !listQuery.isError && rows.length === 0;
  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const canPageBackward = page > 1 && !listQuery.isFetching;
  const canPageForward = page < totalPages && !listQuery.isFetching;

  const saveMutation = useMutation({
    mutationFn: async () => {
      const token = await getWriteToken();
      const payload = {
        name: form.name,
        description: form.description,
        variables: variablesFromRows(form.variables),
      };
      if (formMode === "create") {
        return createEnvGroup(payload, workspaceId, token);
      }
      return patchEnvGroup(editingId as string, payload, workspaceId, token);
    },
    onSuccess: async () => {
      setPage(1);
      await queryClient.invalidateQueries({
        queryKey: ["env-groups", workspaceId],
      });
      setFormOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    },
    onError: (error) => {
      if (
        error instanceof ApiError &&
        error.body.code === "ENV_GROUP_NAME_CONFLICT"
      ) {
        setFormErrors((current) => ({
          ...current,
          name: "Env Group name already exists.",
        }));
        setFormApiError(null);
        return;
      }
      if (error instanceof ApiError && error.body.code === "VALIDATION_ERROR") {
        const nextErrors: Record<string, string> = {};
        for (const detail of error.body.details ?? []) {
          const field = mapApiValidationField(
            detail.field,
            detail.message,
            form,
          );
          nextErrors[field] = field.includes(".key")
            ? "Check this key and try again."
            : field.includes(".value")
              ? "Check this value and try again."
              : "Check this field and try again.";
        }
        setFormErrors((current) => ({ ...current, ...nextErrors }));
        setFormApiError("Check the highlighted fields and try again.");
        return;
      }
      setFormApiError(errorMessage(error));
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: async (envGroupId: string) =>
      duplicateEnvGroup(envGroupId, workspaceId, await getWriteToken()),
    onSuccess: async () => {
      setPage(1);
      await queryClient.invalidateQueries({
        queryKey: ["env-groups", workspaceId],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (envGroupId: string) =>
      deleteEnvGroup(envGroupId, workspaceId, await getWriteToken()),
    onSuccess: async () => {
      if (rows.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
      await queryClient.invalidateQueries({
        queryKey: ["env-groups", workspaceId],
      });
      setDeleteTarget(null);
      setDeleteError(null);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.body.code === "ENV_GROUP_IN_USE") {
        setDeleteError(
          "This Env Group is used by a scenario or test plan and cannot be deleted yet.",
        );
        return;
      }
      setDeleteError(errorMessage(error));
    },
  });

  function openCreate() {
    setFormMode("create");
    setEditingId(null);
    setForm(emptyForm);
    setFormErrors({});
    setFormApiError(null);
    setFormOpen(true);
  }

  function updateSearch(value: string) {
    setQ(value);
    setPage(1);
  }

  const workspaceSwitchGuard = useMemo(
    () => ({
      dirty: formOpen && (formMode === "edit" || formHasDraft(form)),
      safePath: "/assets/env-groups",
      onAbandon: () => {
        setFormOpen(false);
        setEditingId(null);
        setForm(emptyForm);
        setFormErrors({});
        setFormApiError(null);
      },
    }),
    [form, formMode, formOpen],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);

  if (session === null) {
    return null;
  }

  function openEdit(group: EnvGroupSummary) {
    setFormMode("edit");
    setEditingId(group.id);
    setForm(emptyForm);
    setFormErrors({});
    setFormApiError(null);
    setFormOpen(true);
  }

  function updateVariable(
    id: string,
    field: "key" | "value" | "type",
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      variables: current.variables.map((row) =>
        row.id === id ? { ...row, [field]: value } : row,
      ),
    }));
  }

  function removeVariable(id: string) {
    setForm((current) => ({
      ...current,
      variables: current.variables.filter((row) => row.id !== id),
    }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormApiError(null);
    const nextErrors = validateForm(form);
    setFormErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    try {
      await saveMutation.mutateAsync();
    } catch {
      // Mutation onError owns user-visible API errors.
    }
  }

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-[34px] font-semibold leading-10 text-white">
            Env Groups
          </h1>
          <p className="mt-2 text-base leading-6 text-text-muted">
            Reusable variables for scenarios and test plans.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={openCreate}
          type="button"
        >
          <Plus className="h-4 w-4" />
          New Env Group
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block w-full max-w-md">
          <span className="sr-only">Search Env Groups</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <input
            className="h-11 w-full rounded-lg border border-white/10 bg-surface-container-low px-10 text-sm text-text-main outline-none transition placeholder:text-secondary focus:border-primary/50"
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Search by name..."
            value={q}
          />
        </label>
        <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
          Sort: <span className="text-text-main">Newest first</span>
        </div>
      </div>

      <section className="surgepilot-glass overflow-hidden rounded-xl">
        {listQuery.isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            Loading Env Groups...
          </div>
        ) : null}
        {listQuery.isError ? (
          <div className="flex items-center justify-between gap-4 p-8">
            <p className="text-sm text-error">
              {errorMessage(listQuery.error)}
            </p>
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
              onClick={() => listQuery.refetch()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
          </div>
        ) : null}
        {isEmpty ? (
          <div className="mx-auto flex max-w-md flex-col items-center p-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-lg border border-primary/20 bg-primary-container/10 font-mono text-sm font-bold text-primary">
              ENV
            </div>
            <h2 className="mt-5 text-lg font-semibold leading-7 text-white">
              No Env Groups yet
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Create an Env Group to reuse variables across scenarios and test
              plans.
            </p>
          </div>
        ) : null}
        {rows.length > 0 ? (
          <>
            <table className="w-full border-collapse text-left">
              <thead className="border-b border-white/10 bg-white/5">
                <tr>
                  {[
                    "Name",
                    "Description",
                    "Variables",
                    "In use",
                    "Updated at",
                    "Actions",
                  ].map((heading) => (
                    <th
                      className="px-5 py-4 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-secondary"
                      key={heading}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {rows.map((group) => (
                  <tr
                    className="transition hover:bg-white/[0.03]"
                    key={group.id}
                  >
                    <td className="px-5 py-4 font-semibold text-white">
                      {group.name}
                    </td>
                    <td className="max-w-md px-5 py-4 text-sm text-text-muted">
                      {group.description || "No description"}
                    </td>
                    <td className="px-5 py-4">
                      <span className="rounded-full border border-primary/20 bg-primary-container/10 px-3 py-1 font-mono text-xs text-primary">
                        {group.variableCount}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-sm text-text-muted">
                      {group.inUse ? "Yes" : "No"}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text-muted">
                      {formatDate(group.updatedAt)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <IconButton
                          label={`Edit ${group.name}`}
                          onClick={() => openEdit(group)}
                        >
                          <Pencil className="h-4 w-4" />
                        </IconButton>
                        <IconButton
                          disabled={duplicateMutation.isPending}
                          label={`Duplicate ${group.name}`}
                          onClick={() => duplicateMutation.mutate(group.id)}
                        >
                          <Copy className="h-4 w-4" />
                        </IconButton>
                        <IconButton
                          label={`Delete ${group.name}`}
                          onClick={() => setDeleteTarget(group)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
              <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
                Page <span className="text-text-main">{page}</span> of{" "}
                <span className="text-text-main">{totalPages}</span>
              </div>
              <div className="flex gap-2">
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canPageBackward}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  type="button"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous page
                </button>
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canPageForward}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next page
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      <Dialog.Root onOpenChange={setFormOpen} open={formOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
          <Dialog.Content className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-3xl flex-col border-l border-white/10 bg-surface-container-low shadow-2xl">
            <div className="flex items-start justify-between border-b border-white/10 p-6">
              <div>
                <Dialog.Title className="text-xl font-semibold text-white">
                  {formMode === "create"
                    ? "Create Env Group"
                    : "Edit Env Group"}
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-text-muted">
                  Add plain variables or write-only secrets that scenarios and
                  test plans can reuse.
                </Dialog.Description>
              </div>
              <Dialog.Close className="rounded-lg p-2 text-secondary transition hover:bg-white/5 hover:text-white">
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>

            {formMode === "edit" && detailQuery.isLoading ? (
              <div className="p-6 text-sm text-text-muted">
                Loading Env Group...
              </div>
            ) : null}
            {formMode === "edit" && detailQuery.isError ? (
              <div className="p-6 text-sm text-error">
                {errorMessage(detailQuery.error)}
              </div>
            ) : null}

            {(formMode === "create" || detailQuery.data) && (
              <form
                className="flex min-h-0 flex-1 flex-col"
                onSubmit={handleSubmit}
              >
                <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
                  {formApiError ? (
                    <div className="rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                      {formApiError}
                    </div>
                  ) : null}
                  <Field label="Name" error={formErrors.name}>
                    <input
                      className={inputClass(Boolean(formErrors.name))}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                      value={form.name}
                    />
                  </Field>
                  <Field label="Description" error={formErrors.description}>
                    <textarea
                      className={cn(
                        inputClass(Boolean(formErrors.description)),
                        "min-h-24 resize-y py-3",
                      )}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          description: event.target.value,
                        }))
                      }
                      value={form.description}
                    />
                  </Field>

                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-white">
                        Variables
                      </h3>
                      <button
                        className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            variables: [
                              emptyVariableRow(),
                              ...current.variables,
                            ],
                          }))
                        }
                        type="button"
                      >
                        <Plus className="h-4 w-4" />
                        Add variable
                      </button>
                    </div>
                    {formErrors.variables ? (
                      <p className="mb-3 text-sm text-error">
                        {formErrors.variables}
                      </p>
                    ) : null}
                    <div className="space-y-3">
                      {form.variables.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-white/10 p-5 text-sm text-text-muted">
                          No variables. Empty groups are allowed.
                        </div>
                      ) : null}
                      {form.variables.map((row) => (
                        <div
                          className="grid grid-cols-[1fr_1fr_auto] items-start gap-3"
                          key={row.id}
                        >
                          <Field
                            label="Key"
                            error={formErrors[`variables.${row.id}.key`]}
                          >
                            <input
                              className={inputClass(
                                Boolean(formErrors[`variables.${row.id}.key`]),
                              )}
                              onChange={(event) =>
                                updateVariable(
                                  row.id,
                                  "key",
                                  event.target.value,
                                )
                              }
                              value={row.key}
                            />
                          </Field>
                          <Field
                            label={
                              row.type === "secret" ? "Secret value" : "Value"
                            }
                            error={formErrors[`variables.${row.id}.value`]}
                          >
                            <input
                              className={inputClass(
                                Boolean(
                                  formErrors[`variables.${row.id}.value`],
                                ),
                              )}
                              onChange={(event) =>
                                updateVariable(
                                  row.id,
                                  "value",
                                  event.target.value,
                                )
                              }
                              placeholder={
                                row.type === "secret" && row.hasExistingSecret
                                  ? "******** (leave blank to keep)"
                                  : undefined
                              }
                              type={row.type === "secret" ? "password" : "text"}
                              value={row.value}
                            />
                          </Field>
                          <div>
                            <span className="mb-1.5 block text-sm font-medium text-text-main">
                              Actions
                            </span>
                            <div className="flex h-10 items-center gap-3">
                              <label className="inline-flex items-center gap-2 text-sm text-text-muted">
                                <input
                                  checked={row.type === "secret"}
                                  onChange={(event) =>
                                    updateVariable(
                                      row.id,
                                      "type",
                                      event.target.checked ? "secret" : "plain",
                                    )
                                  }
                                  type="checkbox"
                                />
                                Secret
                              </label>
                              <IconButton
                                label={`Remove ${row.key || "variable"}`}
                                onClick={() => removeVariable(row.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </IconButton>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-3 border-t border-white/10 p-6">
                  <Dialog.Close className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main">
                    Cancel
                  </Dialog.Close>
                  <button
                    className="rounded-lg bg-primary-container px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={saveMutation.isPending}
                    type="submit"
                  >
                    {saveMutation.isPending ? "Saving" : "Save Env Group"}
                  </button>
                </div>
              </form>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        open={deleteTarget !== null}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(420px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <Dialog.Title className="text-lg font-semibold text-white">
              Delete Env Group
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
              Delete {deleteTarget?.name}? This action cannot be undone.
            </Dialog.Description>
            {deleteError ? (
              <p className="mt-4 text-sm text-error">{deleteError}</p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main">
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-error-container px-4 py-2 text-sm font-semibold text-on-error-container disabled:cursor-not-allowed disabled:opacity-60"
                disabled={deleteMutation.isPending}
                onClick={() =>
                  deleteTarget && deleteMutation.mutate(deleteTarget.id)
                }
                type="button"
              >
                {deleteMutation.isPending ? "Deleting" : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function inputClass(hasError: boolean) {
  return cn(
    "h-10 w-full rounded-lg border bg-surface-container px-3 text-sm text-text-main outline-none transition focus:border-primary/50",
    hasError ? "border-error/60" : "border-white/10",
  );
}

function Field({
  children,
  error,
  label,
}: Readonly<{ children: React.ReactNode; error?: string; label: string }>) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-text-main">
        {label}
      </span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-error">{error}</span>
      ) : null}
    </label>
  );
}

function IconButton({
  children,
  disabled,
  label,
  onClick,
}: Readonly<{
  children: React.ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}>) {
  return (
    <button
      aria-label={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}
