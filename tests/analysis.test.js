const { analyseSeverity } = require("../src/analysis");

describe("analyseSeverity", () => {
  test("returns critical for life-threatening keywords", () => {
    expect(analyseSeverity("He is not breathing and dying")).toBe("critical");
    expect(analyseSeverity("There was a gunshot")).toBe("critical");
    expect(analyseSeverity("Person is unconscious and unresponsive")).toBe("critical");
  });

  test("returns high for serious emergency keywords", () => {
    expect(analyseSeverity("There is a large fire in the building")).toBe("high");
    expect(analyseSeverity("Someone has chest pain")).toBe("high");
    expect(analyseSeverity("I witnessed an assault with a weapon")).toBe("high");
  });

  test("returns medium for moderate emergency keywords", () => {
    expect(analyseSeverity("There was a car accident")).toBe("medium");
    expect(analyseSeverity("I smell a gas leak")).toBe("medium");
    expect(analyseSeverity("Someone is bleeding from a small cut")).toBe("medium");
  });

  test("returns low for non-emergency keywords", () => {
    expect(analyseSeverity("I have a noise complaint")).toBe("low");
    expect(analyseSeverity("I found a lost pet")).toBe("low");
  });

  test("returns medium for unrecognised input", () => {
    expect(analyseSeverity("hello world")).toBe("medium");
  });

  test("returns low for empty or missing input", () => {
    expect(analyseSeverity("")).toBe("low");
    expect(analyseSeverity(null)).toBe("low");
    expect(analyseSeverity(undefined)).toBe("low");
  });

  test("is case-insensitive", () => {
    expect(analyseSeverity("HEART ATTACK")).toBe("critical");
    expect(analyseSeverity("Fire")).toBe("high");
  });
});
