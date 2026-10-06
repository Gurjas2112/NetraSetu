import { useTranslation } from "react-i18next";

export default function QualityRing({
  score,
  previewUrl,
}: {
  score: number;
  previewUrl: string | null;
}) {
  const { t } = useTranslation();
  const ready = score >= 0.55;
  const colour = ready ? "var(--dx-routine)" : "var(--nx-slate-400)";
  return (
    <div className="relative mx-auto h-56 w-56">
      <div
        data-testid="quality-ring"
        data-ready={ready ? "true" : "false"}
        role="img"
        className="absolute inset-0 rounded-full"
        style={{ boxShadow: `inset 0 0 0 8px ${colour}` }}
        aria-label={ready ? t("field.ring.ready") : t("field.ring.hold")}
      />
      {previewUrl ? (
        <img
          src={previewUrl}
          alt=""
          className="absolute inset-4 h-[calc(100%-2rem)] w-[calc(100%-2rem)] rounded-full object-cover"
        />
      ) : (
        <div
          className="absolute inset-4 rounded-full"
          style={{ background: "var(--nx-slate-200)" }}
        />
      )}
    </div>
  );
}
