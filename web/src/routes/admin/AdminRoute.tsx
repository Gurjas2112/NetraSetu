import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { health, type Health } from "../../api/client";

export default function AdminRoute() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    health()
      .then((h) => !cancelled && setStatus(h))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1 style={{ font: "var(--t-h1)" }}>{t("admin.title")}</h1>
      {failed ? (
        <p role="alert" className="mt-4">
          {t("admin.unreachable")}
        </p>
      ) : !status ? (
        <p className="mt-4">{t("admin.loading")}</p>
      ) : (
        <dl className="mt-4 grid max-w-md grid-cols-2 gap-2">
          <dt>{t("admin.status")}</dt>
          <dd data-testid="health-status">{status.status}</dd>
          <dt>{t("admin.engine")}</dt>
          <dd style={{ font: "var(--t-data)" }}>{status.engine}</dd>
          <dt>{t("admin.contract")}</dt>
          <dd style={{ font: "var(--t-data)" }}>{status.contractVersion}</dd>
        </dl>
      )}
    </div>
  );
}
