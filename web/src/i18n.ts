import i18n from "i18next";
import { initReactI18next } from "react-i18next";

export const SUPPORTED_LANGUAGES = ["en", "hi", "mr"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

async function loadBundle(lng: string): Promise<void> {
  if (i18n.hasResourceBundle(lng, "translation")) return;
  const response = await fetch(`/locales/${lng}.json`);
  if (!response.ok) throw new Error(`cannot load locale ${lng}`);
  i18n.addResourceBundle(lng, "translation", (await response.json()) as object);
}

export async function initI18n(): Promise<void> {
  await i18n.use(initReactI18next).init({
    resources: {},
    lng: "en",
    fallbackLng: "en",
    supportedLngs: [...SUPPORTED_LANGUAGES],
    interpolation: { escapeValue: false },
  });
  await loadBundle("en");
  await i18n.changeLanguage("en");
}

export async function setLanguage(lng: Language): Promise<void> {
  await loadBundle(lng);
  await i18n.changeLanguage(lng);
}

export default i18n;
