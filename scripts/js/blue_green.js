"use strict";

const VALID_SLOTS = new Set(["blue", "green"]);

function normalizeSlot(value) {
  if (typeof value !== "string") {
    throw new Error("Environment slot must be a string");
  }

  const slot = value.trim().toLowerCase();
  if (!VALID_SLOTS.has(slot)) {
    throw new Error(`Unsupported environment slot: ${value}`);
  }

  return slot;
}

function resolveCandidateSlot(activeSlot) {
  const active = normalizeSlot(activeSlot);
  return active === "blue" ? "green" : "blue";
}

function buildDeploymentPlan(activeSlot, imageTag) {
  if (!imageTag || typeof imageTag !== "string") {
    throw new Error("A non-empty image tag is required");
  }

  const active = normalizeSlot(activeSlot);
  const candidate = resolveCandidateSlot(active);

  return {
    active,
    candidate,
    imageTag: imageTag.trim(),
    smokePath: "/health",
  };
}

module.exports = {
  buildDeploymentPlan,
  normalizeSlot,
  resolveCandidateSlot,
};
