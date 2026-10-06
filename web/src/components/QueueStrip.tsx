import { useTranslation } from "react-i18next";

export default function QueueStrip({
  screened,
  waiting,
  lastSync,
}: {
  screened: number;
  waiting: number;
  lastSync: Date | null;
}) {
  const { t } = useTranslation();
  const syncLabel = lastSync
    ? lastSync.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : t("queue.never");
  return (
    <p
      data-testid="queue-strip"
      className="flex flex-wrap gap-2"
      style={{ font: "var(--t-caption)", color: "var(--nx-slate-700)" }}
    >
      <span>{t("queue.screened", { count: screened })}</span>
      <span aria-hidden="true">·</span>
      <span data-testid="sync-waiting">{t("queue.waiting", { count: waiting })}</span>
      <span aria-hidden="true">·</span>
      <span>{t("queue.lastSync", { time: syncLabel })}</span>
    </p>
  );
}
