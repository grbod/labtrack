import { describe, expect, it } from "vitest"

import { RESULT_IMPORTER_EXISTING_RESULTS_PAGE_SIZE } from "./resultsImporterConfig"

describe("results importer config", () => {
  it("uses a test-results page size accepted by the backend endpoint", () => {
    expect(RESULT_IMPORTER_EXISTING_RESULTS_PAGE_SIZE).toBeLessThanOrEqual(100)
  })
})
