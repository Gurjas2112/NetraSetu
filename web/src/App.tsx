import { useTranslation } from "react-i18next";

export default function App() {
  const { t } = useTranslation();
  return (
    <main className="p-6">
      <h1 style={{ font: "var(--t-h1)" }}>{t("app.title")}</h1>
      <p>{t("app.tagline")}</p>
    </main>
  );
}
