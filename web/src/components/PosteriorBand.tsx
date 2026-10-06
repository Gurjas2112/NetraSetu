import { useTranslation } from "react-i18next";

const GRADE_FILL = [
  "var(--nx-slate-400)",
  "var(--nx-slate-700)",
  "var(--dx-refer)",
  "var(--dx-refer)",
  "var(--lx-neovasc)",
] as const;

export default function PosteriorBand({
  posterior,
  threshold,
}: {
  posterior: number[] | null | undefined;
  threshold?: number | null;
}) {
  const { t } = useTranslation();
  if (!posterior || posterior.length !== 5) {
    return (
      <section data-testid="posterior-band">
        <p style={{ font: "var(--t-caption)" }}>{t("posterior.empty")}</p>
      </section>
    );
  }
  const referable = (posterior[2] ?? 0) + (posterior[3] ?? 0) + (posterior[4] ?? 0);
  const showLine = typeof threshold === "number" && Number.isFinite(threshold);
  return (
    <section data-testid="posterior-band">
      <div className="flex" style={{ height: "1.25rem" }} role="img" aria-label={t("posterior.label")}>
        {posterior.map((p, grade) => (
          <div
            key={grade}
            data-testid="posterior-segment"
            data-grade={grade}
            style={{
              width: `${p * 100}%`,
              background: GRADE_FILL[grade],
            }}
            title={t(`grade.${grade}`)}
          />
        ))}
      </div>
      {showLine ? (
        <div className="relative h-3">
          <div
            data-testid="posterior-threshold"
            className="absolute top-0 h-3 w-px"
            style={{
              left: `${(threshold as number) * 100}%`,
              background: "var(--nx-slate-900)",
            }}
          />
        </div>
      ) : null}
      <p data-testid="posterior-referable" style={{ font: "var(--t-data)", fontVariantNumeric: "tabular-nums" }}>
        {t("posterior.referable")} {referable.toFixed(2)}
      </p>
    </section>
  );
}
