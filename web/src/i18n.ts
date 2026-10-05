import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../public/locales/en.json";
import hi from "../public/locales/hi.json";
import mr from "../public/locales/mr.json";

export const SUPPORTED_LANGUAGES = ["en", "hi", "mr"] as const;

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
