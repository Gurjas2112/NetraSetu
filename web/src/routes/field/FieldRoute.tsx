import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { analyze, ApiError, type Study } from "../../api/client";
import DecisionBanner from "../../components/DecisionBanner";

type Status = "idle" | "assessing" | "error";

export default function FieldRoute({
  study,
  onStudy,
}: {
  study: Study | null;
  onStudy: (study: Study | null) => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [patientRef, setPatientRef] = useState("demo-patient-001");
  const [consentId, setConsentId] = useState("demo-consent-001");
  const [status, setStatus] = useState<Status>("idle");
  const [errorKey, setErrorKey] = useState<string>("field.error.generic");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    setStatus("assessing");
    onStudy(null);
    try {
      onStudy(await analyze(file, patientRef, consentId));
      setStatus("idle");
    } catch (err) {
      setErrorKey(
        err instanceof ApiError && err.status === 503
          ? "field.error.unavailable"
          : "field.error.generic",
      );
      setStatus("error");
    }
  };

  return (
    <div>
      <h1 style={{ font: "var(--t-h1)" }}>{t("field.title")}</h1>
      <form onSubmit={submit} className="mt-4 flex max-w-md flex-col gap-3">
        <label className="flex flex-col gap-1">
          {t("field.patientRef")}
          <input
            className="border p-2"
            style={{ borderColor: "var(--nx-slate-400)" }}
            value={patientRef}
            onChange={(e) => setPatientRef(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("field.consentId")}
          <input
            className="border p-2"
            style={{ borderColor: "var(--nx-slate-400)" }}
            value={consentId}
            onChange={(e) => setConsentId(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("field.image")}
          <input
            data-testid="file-input"
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        <button
          type="submit"
          disabled={!file || status === "assessing"}
          className="p-3 disabled:opacity-50"
          style={{ background: "var(--nx-signal)", color: "var(--nx-paper)" }}
        >
          {status === "assessing" ? t("field.assessing") : t("field.submit")}
        </button>
      </form>

      {status === "error" ? (
        <p role="alert" className="mt-4" style={{ color: "var(--dx-refer)" }}>
          {t(errorKey)}
        </p>
      ) : null}

      {study ? (
        <>
          <DecisionBanner decision={study.decision} guidanceKey={study.retakeGuidanceKey} />
          {study.criteria.length > 0 ? (
            <details>
              <summary>{t("field.why", { count: study.criteria.length })}</summary>
              <ul className="list-disc pl-6">
                {study.criteria.map((c) => (
                  <li key={c.key}>{t(c.key)}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
