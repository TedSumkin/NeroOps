import { describe, expect, it } from "vitest";

import { entryDefinitions, entryOrder } from "./entryConfig";

describe("entry definitions", () => {
  it("defines every entry type exactly once", () => {
    expect(entryOrder).toHaveLength(9);
    expect(new Set(entryOrder).size).toBe(entryOrder.length);
    expect(Object.keys(entryDefinitions).sort()).toEqual([...entryOrder].sort());
  });

  it("requires the core fields used by the backend", () => {
    expect(entryDefinitions.feeding.fields.find((field) => field.name === "food")?.required).toBe(
      true,
    );
    expect(
      entryDefinitions.symptom.fields.find((field) => field.name === "severity")?.required,
    ).toBe(true);
    expect(
      entryDefinitions.weight.fields.find((field) => field.name === "weight_kg")?.required,
    ).toBe(true);
  });
});

