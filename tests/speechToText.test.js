const { transcribe } = require("../src/ivr/speechToText");

describe("speechToText (stub mode – no Google credentials)", () => {
  test("returns input text as transcript in stub mode", async () => {
    const result = await transcribe("there is a fire help me", "en-US");
    expect(result.text).toBe("there is a fire help me");
    expect(result.languageCode).toBe("en");
  });

  test("extracts language from hint", async () => {
    const result = await transcribe("auxilio", "es-MX");
    expect(result.languageCode).toBe("es");
  });

  test("defaults to en-US hint", async () => {
    const result = await transcribe("emergency");
    expect(result.languageCode).toBe("en");
  });
});
