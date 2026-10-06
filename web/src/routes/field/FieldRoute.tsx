import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { analyze, ApiError, giveConsent, sha256Hex, type Consent, type Study } from "../../api/client";
import DecisionBanner from "../../components/DecisionBanner";
import type { Language } from "../../i18n";

type Status = "idle" | "assessing" | "error";

function errorKeyFor(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) return "field.error.unavailable";
  if (err instanceof ApiError && err.status === 401) return "field.error.unauthorized";
  return "field.error.generic";
}

export default function FieldRoute({
  study,
  onStudy,
}: {
  study: Study | null;
  onStudy: (study: Study | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  // One consent per patient, held in memory for retakes; never persisted.
  const [patient, setPatient] = useState<Consent | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorKey, setErrorKey] = useState<string>("field.error.generic");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || (!patient && !agreed)) return;
    setStatus("assessing");
    onStudy(null);
    try {
      let current = patient;
      if (!current) {
        const notice = t("field.consentNotice");
        current = await giveConsent({
          purpose: "screening",
          noticeHash: await sha256Hex(notice),
          language: i18n.language as Language,
        });
        setPatient(current);
      }
      onStudy(await analyze(file, current.patientRef, current.consentId));
      setStatus("idle");
    } catch (err) {
      setErrorKey(errorKeyFor(err));
      setStatus("error");
    }
  };

  const newPatient = () => {
    setPatient(null);
    setAgreed(false);
    setFile(null);
    onStudy(null);
    setStatus("idle");
  };

  return (
    <div>
      <h1 style={{ font: "var(--t-h1)" }}>{t("field.title")}</h1>
      <form onSubmit={submit} className="mt-4 flex max-w-md flex-col gap-3">
        {patient ? null : (
          <fieldset className="flex flex-col gap-2 border p-3" style={{ borderColor: "var(--nx-slate-200)" }}>
            <p data-testid="consent-notice">{t("field.consentNotice")}</p>
            <label className="flex items-center gap-2">
              <input
                data-testid="consent-given"
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                required
              />
              {t("field.consentGiven")}
            </label>
          </fieldset>
        )}
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
          disabled={!file || (!patient && !agreed) || status === "assessing"}
          className="p-3 disabled:opacity-50"
          style={{ background: "var(--nx-signal)", color: "var(--nx-paper)" }}
        >
          {status === "assessing" ? t("field.assessing") : t("field.submit")}
        </button>
        {patient ? (
          <button type="button" onClick={newPatient} className="p-2 underline">
            {t("field.newPatient")}
          </button>
        ) : null}
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
