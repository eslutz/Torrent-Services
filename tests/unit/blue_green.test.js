"use strict";

const {
  buildDeploymentPlan,
  normalizeSlot,
  resolveCandidateSlot,
} = require("../../scripts/js/blue_green");

describe("blue/green deployment helpers", () => {
  test("normalizes valid slots", () => {
    expect(normalizeSlot(" BLUE ")).toBe("blue");
    expect(normalizeSlot("green")).toBe("green");
  });

  test("rejects invalid slots", () => {
    expect(() => normalizeSlot("red")).toThrow("Unsupported environment slot");
  });

  test("picks the opposite candidate slot", () => {
    expect(resolveCandidateSlot("blue")).toBe("green");
    expect(resolveCandidateSlot("green")).toBe("blue");
  });

  test("builds a deployment plan object", () => {
    expect(buildDeploymentPlan("blue", "v1.2.3")).toEqual({
      active: "blue",
      candidate: "green",
      imageTag: "v1.2.3",
      smokePath: "/health",
    });
  });
});
