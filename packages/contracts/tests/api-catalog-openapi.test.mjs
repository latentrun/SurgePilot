import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const openapi = JSON.parse(readFileSync(new URL("../openapi/api.openapi.json", import.meta.url)));

test("P2-00 API Catalog OpenAPI contract is generated with scoped operations", () => {
  const paths = openapi.paths;
  assert.equal(paths["/v1/api-catalog/specs"].get.operationId, "listApiCatalogSpecs");
  assert.equal(paths["/v1/api-catalog/specs"].post.operationId, "uploadApiCatalogSpec");
  assert.equal(paths["/v1/api-catalog/specs/{specId}"].get.operationId, "getApiCatalogSpec");
  assert.equal(paths["/v1/api-catalog/specs/{specId}"].delete.operationId, "deleteApiCatalogSpec");
  assert.equal(paths["/v1/api-catalog/specs/{specId}/content"].get.operationId, "getApiCatalogSpecContent");
  assert.ok(openapi.components.schemas.ApiCatalogSpecListResponse.properties.items);
  assert.ok(openapi.components.schemas.ApiCatalogSpecSummary.properties.sourceFormat);
  assert.deepEqual(
    openapi.components.schemas.ApiCatalogSpecSourceFormat.enum,
    ["openapi_json", "openapi_yaml", "swagger_json", "swagger_yaml"],
  );
});
