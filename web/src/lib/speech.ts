import type { Language } from "../i18n";

const LANG: Record<Language, string> = {
  en: "en-IN",
  hi: "hi-IN",
  mr: "mr-IN",
};

export function speak(text: string, language: Language): void {
  if (typeof speechSynthesis === "undefined") return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = LANG[language];
  utterance.rate = 0.95;
  speechSynthesis.speak(utterance);
}
