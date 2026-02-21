const { buildSummary } = require("../src/summary");

describe("buildSummary", () => {
  const baseData = {
    callId: "abc-123",
    callerNumber: "+15551234567",
    transcript: "There is a fire in my building",
    translation: null,
    severity: "high",
    responder: "fire",
    latitude: 40.7128,
    longitude: -74.006,
  };

  test("includes all required fields", () => {
    const summary = buildSummary(baseData);
    expect(summary).toContain("abc-123");
    expect(summary).toContain("+15551234567");
    expect(summary).toContain("HIGH");
    expect(summary).toContain("FIRE");
    expect(summary).toContain("There is a fire in my building");
  });

  test("includes location coordinates and map link", () => {
    const summary = buildSummary(baseData);
    expect(summary).toContain("40.7128, -74.006");
    expect(summary).toContain("https://maps.google.com/?q=40.7128,-74.006");
  });

  test("omits location when not provided", () => {
    const data = { ...baseData, latitude: undefined, longitude: undefined };
    const summary = buildSummary(data);
    expect(summary).not.toContain("Location");
    expect(summary).not.toContain("Map link");
  });

  test("includes translation section when translation is provided", () => {
    const data = { ...baseData, translation: "Hay un incendio en mi edificio" };
    const summary = buildSummary(data);
    expect(summary).toContain("Translation (EN)");
    expect(summary).toContain("Hay un incendio en mi edificio");
  });

  test("omits translation section when translation is null", () => {
    const summary = buildSummary(baseData);
    expect(summary).not.toContain("Translation");
  });
});
