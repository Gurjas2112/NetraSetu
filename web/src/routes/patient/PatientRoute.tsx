import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { redeemPatientToken, type PatientView, type Study } from "../../api/client";
import type { Language } from "../../i18n";
import { speak } from "../../lib/speech";

const LAY_KEY = { REFER: "refer", ROUTINE: "routine", RETAKE: "retake" } as const;

export default function PatientRoute({
  study,
  token,
}: {
  study: Study | null;
  token: string | null;
}) {
  const { t, i18n } = useTranslation();
  const [clinical, setClinical] = useState(false);
  const [fromToken, setFromToken] = useState<PatientView | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    redeemPatientToken(token)
      .then((view) => {
        if (!cancelled) setFromToken(view);
      })
      .catch(() => {
        if (!cancelled) setGone(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const decision = fromToken?.decision ?? study?.decision ?? null;
  const empty = !decision && !gone;

  const readAloud = () => {
    if (!decision) return;
    const key = LAY_KEY[decision];
    speak(
      [
        t("patient.found.heading"),
        t(`patient.found.${key}`),
        t("patient.next.heading"),
        t(`patient.next.${key}`),
        t("patient.where.heading"),
        t("patient.where.slot"),
      ].join(". "),
      i18n.language as Language,
    );
  };

  return (
    <div className="max-w-md">
      <h1 style={{ font: "var(--t-h1)" }}>{t("patient.title")}</h1>
      {gone ? (
        <p role="alert" className="mt-4">
          {t("patient.gone")}
        </p>
      ) : empty ? (
        <p className="mt-4">{t("patient.empty")}</p>
      ) : decision ? (
        <div className="mt-4 flex flex-col gap-4">
          <button type="button" onClick={readAloud} className="self-start underline" data-testid="patient-read">
            {t("patient.readAloud")}
          </button>
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.found.heading")}</h2>
            <p>{t(`patient.found.${LAY_KEY[decision]}`)}</p>
            {study ? (
              <button type="button" className="mt-2 underline" onClick={() => setClinical((v) => !v)}>
                {clinical ? t("patient.hideClinical") : t("patient.showClinical")}
              </button>
            ) : null}
            {clinical && study ? (
              <p data-testid="patient-clinical" className="mt-2" style={{ font: "var(--t-data)" }}>
                {study.grade === null ? t("review.none") : t(`grade.${study.grade}`)} · {study.decision}
              </p>
            ) : null}
          </section>
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.next.heading")}</h2>
            <p>{t(`patient.next.${LAY_KEY[decision]}`)}</p>
          </section>
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.where.heading")}</h2>
            <p>{t("patient.where.pending")}</p>
            <p data-testid="patient-slot" className="mt-2 font-semibold">
              {t("patient.where.slot")}
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
