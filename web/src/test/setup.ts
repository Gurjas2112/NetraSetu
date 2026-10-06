import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import "@testing-library/jest-dom/vitest";
import en from "../../public/locales/en.json";

await i18n.use(initReactI18next).init({
  lng: "en",
  fallbackLng: "en",
  resources: { en: { translation: en } },
  interpolation: { escapeValue: false },
});
