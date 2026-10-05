import { useTranslation } from "react-i18next";
import type { Study } from "../../api/client";

export default function ReviewRoute({ study }: { study: Study | null }) {
  const { t } = useTranslation();
  return (
    <div>
      <h1 style={{ font: "var(--t-h1)" }}>{t("review.title")}</h1>
      {!study ? (
        <p className="mt-4">{t("review.empty")}</p>
      ) : (
        <dl className="mt-4 grid max-w-lg grid-cols-2 gap-2">
          <dt>{t("review.decision")}</dt>
          <dd data-testid="review-decision">{study.decision}</dd>
          <dt>{t("review.grade")}</dt>
          <dd>{study.grade === null ? t("review.none") : t(`grade.${study.grade}`)}</dd>
          <dt>{t("review.pReferable")}</dt>
          <dd style={{ font: "var(--t-data)", fontVariantNumeric: "tabular-nums" }}>
            {study.pReferable === null ? t("review.none") : study.pReferable.toFixed(2)}
          </dd>
          <dt>{t("review.reviewRequired")}</dt>
          <dd>{study.reviewRequired ? t("review.yes") : t("review.no")}</dd>
          <dt>{t("review.criteria")}</dt>
          <dd>
            {study.criteria.length === 0 ? (
              t("review.none")
            ) : (
              <ul>
                {study.criteria.map((c) => (
                  <li key={c.key}>{t(c.key)}</li>
                ))}
              </ul>
            )}
          </dd>
          <dt>{t("review.modelVer")}</dt>
          <dd style={{ font: "var(--t-data)" }}>{study.modelVer}</dd>
        </dl>
      )}
    </div>
  );
}
