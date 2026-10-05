import { useTranslation } from "react-i18next";
import type { Study } from "../../api/client";

const LAY_KEY = { REFER: "refer", ROUTINE: "routine", RETAKE: "retake" } as const;

export default function PatientRoute({ study }: { study: Study | null }) {
  const { t } = useTranslation();
  return (
    <div className="max-w-md">
      <h1 style={{ font: "var(--t-h1)" }}>{t("patient.title")}</h1>
      {!study ? (
        <p className="mt-4">{t("patient.empty")}</p>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.found.heading")}</h2>
            <p>{t(`patient.found.${LAY_KEY[study.decision]}`)}</p>
          </section>
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.next.heading")}</h2>
            <p>{t(`patient.next.${LAY_KEY[study.decision]}`)}</p>
          </section>
          <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }}>
            <h2 className="font-semibold">{t("patient.where.heading")}</h2>
            <p>{t("patient.where.pending")}</p>
          </section>
        </div>
      )}
    </div>
  );
}
