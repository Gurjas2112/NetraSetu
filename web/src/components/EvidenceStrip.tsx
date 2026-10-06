import { useTranslation } from "react-i18next";
import type { Study } from "../api/client";

type Evidence = NonNullable<Study["evidence"]>[number];

const RING: Record<Evidence["type"], string> = {
  MA: "var(--lx-microan)",
  HE: "var(--lx-haem)",
  EX: "var(--lx-exudate)",
  SE: "var(--lx-cottonwool)",
  NV_PROXY: "var(--lx-neovasc)",
};

export default function EvidenceStrip({ evidence }: { evidence: Evidence[] | null | undefined }) {
  const { t } = useTranslation();
  const items = evidence ?? [];
  if (items.length === 0) {
    return (
      <section data-testid="evidence-strip">
        <h2 style={{ font: "var(--t-caption)", color: "var(--nx-slate-400)" }}>{t("evidence.title")}</h2>
        <p style={{ font: "var(--t-caption)" }}>{t("evidence.empty")}</p>
      </section>
    );
  }
  return (
    <section data-testid="evidence-strip">
      <h2 style={{ font: "var(--t-caption)", color: "var(--nx-slate-400)" }}>
        {t("evidence.heading", { count: items.length })}
      </h2>
      <ul className="flex gap-2 overflow-x-auto py-2">
        {items.map((item, index) => (
          <li
            key={`${item.type}-${item.x}-${item.y}-${index}`}
            className="w-28 shrink-0"
            data-testid="evidence-tile"
            data-type={item.type}
          >
            <div
              className="relative h-28 w-28 overflow-hidden"
              style={{ boxShadow: `inset 0 0 0 3px ${RING[item.type]}` }}
            >
              <img src={item.cropUrl} alt="" className="h-full w-full object-cover" />
            </div>
            <p style={{ font: "var(--t-caption)" }}>{item.type}</p>
            <p style={{ font: "var(--t-caption)", color: "var(--nx-slate-400)" }}>
              {t(`quadrant.${item.quadrant}`)}
              {item.distanceToFoveaDD !== null
                ? ` · ${item.distanceToFoveaDD.toFixed(1)} DD`
                : ""}
            </p>
            {item.criterionKey ? (
              <p style={{ font: "var(--t-caption)" }}>{t(item.criterionKey)}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
