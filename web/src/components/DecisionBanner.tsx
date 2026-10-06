import { useTranslation } from "react-i18next";
import type { Decision } from "../api/client";

const DECISION_COLOUR: Record<Decision, string> = {
  REFER: "var(--dx-refer)",
  ROUTINE: "var(--dx-routine)",
  RETAKE: "var(--dx-retake)",
};

const DECISION_KEY: Record<Decision, string> = {
  REFER: "refer",
  ROUTINE: "routine",
  RETAKE: "retake",
};

export default function DecisionBanner({
  decision,
  guidanceKey,
  attempt,
}: {
  decision: Decision;
  guidanceKey?: string | null;
  attempt?: number | null;
}) {
  const { t } = useTranslation();
  const key = DECISION_KEY[decision];
  return (
    <section aria-live="polite" className="my-4">
      <p
        data-testid="decision"
        data-decision={decision}
        style={{ font: "var(--t-decision)", color: DECISION_COLOUR[decision] }}
      >
        {t(`decision.${key}.title`)}
      </p>
      <p>{t(`decision.${key}.next`)}</p>
      {decision === "RETAKE" && guidanceKey ? (
        <p data-testid="retake-guidance">{t(guidanceKey)}</p>
      ) : null}
      {decision === "RETAKE" && attempt ? (
        <p data-testid="retake-attempt">{t("field.attempt", { n: attempt, max: 3 })}</p>
      ) : null}
    </section>
  );
}
