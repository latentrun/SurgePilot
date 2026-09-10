import type {
  CurlImportStepDraft,
  ScenarioCreateRequest,
  ScenarioDetail,
  ScenarioPatchRequest,
  ScenarioStep,
} from "../../app/api-client";

export type ScenarioNamedValue = NonNullable<
  ScenarioStep["queryParams"]
>[number];
export type ScenarioFormField = NonNullable<
  NonNullable<ScenarioStep["body"]>["formFields"]
>[number];
export type ScenarioUploadFile = NonNullable<
  ScenarioStep["uploadFiles"]
>[number];
export type ScenarioDataSource = NonNullable<
  ScenarioDetail["dataSources"]
>[number];
export type ScenarioExtractor = NonNullable<
  ScenarioStep["extractors"]
>[number];
export type ScenarioAssertion = NonNullable<
  ScenarioStep["assertions"]
>[number];
export type ScenarioScript = NonNullable<ScenarioStep["scripts"]>[number];

export const defaultSettings = {
  thinkTimeMs: 0,
  timeoutMs: 30000,
  followRedirects: true,
  keepAlive: true,
  storeCache: true,
  storeCookie: true,
  retrieveResources: false,
};
const ulid = () =>
  `01HZX3Y9M0E9W7Z6M5QK${Math.random().toString(36).slice(2, 8).toUpperCase()}`.slice(
    0,
    26,
  );

export function newNamedValue(): ScenarioNamedValue {
  return { id: ulid(), name: "", value: "", enabled: true };
}

export function newFormField(): ScenarioFormField {
  return newNamedValue();
}

export function newUploadFile(): ScenarioUploadFile {
  return {
    id: ulid(),
    fieldName: "",
    dependencyFileId: "",
    mimeType: null,
    enabled: true,
  };
}

export function newDataSource(): ScenarioDataSource {
  return {
    id: ulid(),
    dependencyFileId: "",
    displayName: "",
    delimiter: ",",
    quoted: null,
    loop: true,
    variableNames: [],
    randomOrder: false,
    enabled: true,
  };
}

export function newExtractor(
  type: ScenarioExtractor["type"],
): ScenarioExtractor {
  return {
    id: ulid(),
    type,
    variableName: "",
    expression: type === "jsonpath" ? "$." : "",
    defaultValue: "",
    matchNo: 1,
    subject: "body",
    template: type === "regexp" ? "1" : null,
    enabled: true,
  };
}

export function newAssertion(
  type: ScenarioAssertion["type"],
): ScenarioAssertion {
  return {
    id: ulid(),
    type,
    expectedStatus: type === "status_code" ? 200 : null,
    contains: type === "body_contains" ? "" : null,
    jsonpath:
      type === "jsonpath_exists" || type === "jsonpath_equals" ? "$." : null,
    expectedValue: type === "jsonpath_equals" ? "" : null,
    regexp: false,
    not: false,
    enabled: true,
  };
}

export function newScript(execute: ScenarioScript["execute"]): ScenarioScript {
  return {
    id: ulid(),
    execute,
    language: "groovy",
    scriptText: "",
    enabled: true,
  };
}

export function newStep(): ScenarioStep {
  return {
    id: ulid(),
    enabled: true,
    name: "New request",
    method: "GET",
    path: "/",
    queryParams: [],
    headers: [],
    body: { type: "none", contentType: null, rawText: null, formFields: [] },
    uploadFiles: [],
    extractors: [],
    assertions: [
      {
        id: ulid(),
        type: "status_code",
        expectedStatus: 200,
        enabled: true,
        not: false,
        regexp: false,
      },
    ],
    scripts: [],
    settings: {
      thinkTimeMs: null,
      timeoutMs: null,
      followRedirects: null,
      keepAlive: null,
    },
  };
}

function cloneNamedValue<T extends { id: string }>(item: T): T {
  return { ...item, id: ulid() };
}

export function cloneStep(step: ScenarioStep): ScenarioStep {
  const body = step.body ?? {
    type: "none" as const,
    contentType: null,
    rawText: null,
    formFields: [],
  };
  return {
    ...step,
    id: ulid(),
    name: `${step.name} copy`,
    queryParams: (step.queryParams ?? []).map(cloneNamedValue),
    headers: (step.headers ?? []).map(cloneNamedValue),
    body: {
      ...body,
      formFields: (body.formFields ?? []).map(cloneNamedValue),
    },
    uploadFiles: (step.uploadFiles ?? []).map(cloneNamedValue),
    extractors: (step.extractors ?? []).map(cloneNamedValue),
    assertions: (step.assertions ?? []).map(cloneNamedValue),
    scripts: (step.scripts ?? []).map(cloneNamedValue),
    settings: {
      thinkTimeMs: step.settings?.thinkTimeMs ?? null,
      timeoutMs: step.settings?.timeoutMs ?? null,
      followRedirects: step.settings?.followRedirects ?? null,
      keepAlive: step.settings?.keepAlive ?? null,
    },
  };
}

function materializeNamedValue<
  T extends { name: string; value: string; enabled?: boolean },
>(item: T) {
  return {
    id: ulid(),
    name: item.name,
    value: item.value,
    enabled: item.enabled ?? true,
  };
}

/**
 * Materializes a request-only cURL import Step draft into an editable Scenario
 * Step. The API preview never returns persistent IDs, so the merge layer owns
 * every Step and child ID here.
 */
export function stepFromCurlImportDraft(
  draft: CurlImportStepDraft,
  preserveStepId?: string,
): ScenarioStep {
  const base = newStep();
  const body = draft.body ?? {
    type: "none" as const,
    contentType: null,
    rawText: null,
    formFields: [],
  };
  return {
    ...base,
    id: preserveStepId ?? base.id,
    enabled: draft.enabled ?? true,
    name: draft.name,
    method: draft.method,
    path: draft.path,
    queryParams: (draft.queryParams ?? []).map(materializeNamedValue),
    headers: (draft.headers ?? []).map(materializeNamedValue),
    body: {
      type: body.type ?? "none",
      contentType: body.contentType ?? null,
      rawText: body.rawText ?? null,
      formFields: (body.formFields ?? []).map(materializeNamedValue),
    },
    uploadFiles: [],
    extractors: [],
    scripts: [],
    settings: {
      thinkTimeMs: null,
      timeoutMs: draft.settings?.timeoutMs ?? null,
      followRedirects: draft.settings?.followRedirects ?? null,
      keepAlive: draft.settings?.keepAlive ?? null,
    },
  };
}

export function blankScenarioPayload(
  name: string,
  baseUrlExpression = "${base_url}",
): ScenarioCreateRequest {
  return {
    name,
    description: null,
    tags: [],
    baseUrlExpression,
    defaultSettings,
    dataSources: [],
    steps: [],
  };
}
export function toPatchPayload(
  detail: ScenarioDetail,
  expectedRevision: number,
): ScenarioPatchRequest {
  return {
    expectedRevision,
    name: detail.name,
    description: detail.description,
    tags: detail.tags,
    baseUrlExpression: detail.baseUrlExpression,
    defaultSettings: detail.defaultSettings,
    dataSources: detail.dataSources,
    steps: detail.steps,
  };
}
