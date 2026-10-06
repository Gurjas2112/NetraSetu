import { useState } from "react";
import { useTranslation } from "react-i18next";
import { setAccessToken, type Study } from "./api/client";
import { setLanguage, SUPPORTED_LANGUAGES, type Language } from "./i18n";
import { Link, useRoute } from "./router";
import AdminRoute from "./routes/admin/AdminRoute";
import FieldRoute from "./routes/field/FieldRoute";
import PatientRoute from "./routes/patient/PatientRoute";
import ReviewRoute from "./routes/review/ReviewRoute";

export default function App() {
  const { t, i18n } = useTranslation();
  const route = useRoute();
  // Held in memory only: clinical data never goes to localStorage or any cache.
  const [study, setStudy] = useState<Study | null>(null);

  const signOut = async () => {
    setAccessToken(null);
    setStudy(null);
    if (typeof caches !== "undefined") await caches.delete("tiles");
  };

  return (
    <div className="min-h-screen">
      <header
        className="flex flex-wrap items-center gap-4 px-6 py-3"
        style={{ background: "var(--nx-slate-900)", color: "var(--nx-paper)" }}
      >
        <span className="font-semibold">{t("app.title")}</span>
        <nav className="flex gap-4">
          <Link to="/field">{t("nav.field")}</Link>
          <Link to="/review">{t("nav.review")}</Link>
          <Link to="/patient">{t("nav.patient")}</Link>
          <Link to="/admin">{t("nav.admin")}</Link>
        </nav>
        <label className="ml-auto flex items-center gap-2">
          <span>{t("nav.language")}</span>
          <select
            value={i18n.language}
            onChange={(e) => void setLanguage(e.target.value as Language)}
            style={{ background: "var(--nx-slate-700)", color: "var(--nx-paper)" }}
          >
            {SUPPORTED_LANGUAGES.map((lng) => (
              <option key={lng} value={lng}>
                {t(`language.${lng}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void signOut()} className="underline">
          {t("auth.signOut")}
        </button>
      </header>
      <main className={route.path === "/review" ? "" : "p-6"}>
        {route.path === "/field" && <FieldRoute study={study} onStudy={setStudy} />}
        {route.path === "/review" && <ReviewRoute study={study} />}
        {route.path === "/patient" && <PatientRoute study={study} token={route.patientToken} />}
        {route.path === "/admin" && <AdminRoute />}
      </main>
    </div>
  );
}
