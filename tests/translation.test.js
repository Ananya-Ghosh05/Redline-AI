const { translate, detectLanguage } = require("../src/translation");

describe("translation (stub mode – no Google credentials)", () => {
  test("returns original text when source and target are the same", async () => {
    const result = await translate("hello", "en", "en");
    expect(result).toBe("hello");
  });

  test("returns stub translation when source and target differ", async () => {
    const result = await translate("hola mundo", "es", "en");
    expect(result).toContain("[translated:en]");
    expect(result).toContain("hola mundo");
  });

  test("detectLanguage returns English by default in stub mode", async () => {
    const result = await detectLanguage("hello world");
    expect(result).toEqual({ language: "en", confidence: 1.0 });
  });
});
