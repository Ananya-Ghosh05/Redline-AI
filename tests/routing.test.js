const { determineResponder } = require("../src/routing");

describe("determineResponder", () => {
  test("routes medical emergencies to ambulance", () => {
    expect(determineResponder("Someone is having a heart attack")).toBe("ambulance");
    expect(determineResponder("Patient is not breathing")).toBe("ambulance");
    expect(determineResponder("Person has chest pain and difficulty breathing")).toBe("ambulance");
  });

  test("routes fire emergencies to fire department", () => {
    expect(determineResponder("The building is on fire with flames everywhere")).toBe("fire");
    expect(determineResponder("There is smoke coming from the basement")).toBe("fire");
  });

  test("routes criminal activity to police", () => {
    expect(determineResponder("There is a robbery in progress")).toBe("police");
    expect(determineResponder("I see someone suspicious breaking in")).toBe("police");
    expect(determineResponder("Someone is being harassed and threatened")).toBe("police");
  });

  test("returns other for unrecognised input", () => {
    expect(determineResponder("hello")).toBe("other");
    expect(determineResponder("")).toBe("other");
  });

  test("returns other for null or undefined", () => {
    expect(determineResponder(null)).toBe("other");
    expect(determineResponder(undefined)).toBe("other");
  });

  test("picks responder with most keyword matches on mixed input", () => {
    // More medical keywords than police
    const text = "Someone was stabbing a person, they are bleeding and having a seizure, severe injury and pain";
    const result = determineResponder(text);
    expect(result).toBe("ambulance");
  });
});
