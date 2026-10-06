import { describe, expect, it } from "vitest";
import en from "../../public/locales/en.json";
import hi from "../../public/locales/hi.json";
import mr from "../../public/locales/mr.json";
import { flattenKeys } from "./i18nKeys";

describe("i18n key parity", () => {
  it("keeps the same keys in en, hi and mr", () => {
    const english = flattenKeys(en).sort();
    expect(flattenKeys(hi).sort()).toEqual(english);
    expect(flattenKeys(mr).sort()).toEqual(english);
    expect(english.length).toBeGreaterThan(70);
  });
});
