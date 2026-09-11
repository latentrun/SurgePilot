import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const openapi = JSON.parse(readFileSync(new URL("../openapi/api.openapi.json", import.meta.url)));
const generatedClient = readFileSync(new URL("../generated/web-client/index.ts", import.meta.url), "utf8");

test("P2-00 API Catalog contract contains only the scoped lifecycle", () => {
  const { paths, components } = openapi;
  assert.equal(paths["/v1/api-catalog/specs"].get.operationId, "listApiCatalogSpecs");
  assert.equal(paths["/v1/api-catalog/specs"].post.operationId, "uploadApiCatalogSpec");
  assert.equal(paths["/v1/api-catalog/specs/{specId}"].get.operationId, "getApiCatalogSpec");
  assert.equal(paths["/v1/api-catalog/specs/{specId}"].delete.operationId, "deleteApiCatalogSpec");
  assert.equal(
    paths["/v1/api-catalog/specs/{specId}/content"].get.operationId,
    "getApiCatalogSpecContent",
  );
  assert.deepEqual(
    Object.values(paths)
      .flatMap((path) => Object.values(path))
      .map((operation) => operation.operationId)
      .filter((operationId) => operationId?.toLowerCase().includes("api")),
    ["listApiCatalogSpecs", "uploadApiCatalogSpec", "deleteApiCatalogSpec", "getApiCatalogSpec", "getApiCatalogSpecContent"],
  );
  assert.ok(components.schemas.ApiCatalogSpecListResponse.properties.items);
  assert.deepEqual(components.schemas.ApiCatalogSpecSourceFormat.enum, [
    "openapi_json",
    "openapi_yaml",
    "swagger_json",
    "swagger_yaml",
  ]);
  assert.equal(paths["/v1/api-catalog/specs"].post.requestBody.content["multipart/form-data"].schema.required[0], "file");
  for (const operationId of [
    "listApiCatalogSpecs",
    "uploadApiCatalogSpec",
    "getApiCatalogSpec",
    "getApiCatalogSpecContent",
    "deleteApiCatalogSpec",
  ]) {
    assert.match(generatedClient, new RegExp(`\\b${operationId}\\b`));
  }
});
