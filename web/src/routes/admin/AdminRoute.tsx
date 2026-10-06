import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { health, type Health } from "../../api/client";

const EMPTY_BARS = [
  { name: "PHC", value: 0 },
  { name: "CHC", value: 0 },
  { name: "DH", value: 0 },
];

export default function AdminRoute() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  const grafana = import.meta.env.VITE_GRAFANA_URL;

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

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }} data-testid="admin-throughput">
          <h2 className="font-semibold">{t("admin.throughput")}</h2>
          <p style={{ font: "var(--t-caption)", color: "var(--nx-slate-700)" }}>{t("admin.awaitingLive")}</p>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={EMPTY_BARS}>
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Bar dataKey="value" fill="var(--nx-signal)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }} data-testid="admin-gradability">
          <h2 className="font-semibold">{t("admin.gradability")}</h2>
          <p style={{ font: "var(--t-caption)", color: "var(--nx-slate-700)" }}>{t("admin.awaitingLive")}</p>
        </section>
        <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }} data-testid="admin-drift">
          <h2 className="font-semibold">{t("admin.drift")}</h2>
          <p style={{ font: "var(--t-caption)", color: "var(--nx-slate-700)" }}>{t("admin.awaitingLive")}</p>
        </section>
        <section className="border p-4" style={{ borderColor: "var(--nx-slate-200)" }} data-testid="admin-funnel">
          <h2 className="font-semibold">{t("admin.funnel")}</h2>
          <p style={{ font: "var(--t-caption)", color: "var(--nx-slate-700)" }}>{t("admin.awaitingLive")}</p>
        </section>
      </div>

      <section className="mt-8">
        <h2 className="font-semibold">{t("admin.grafana")}</h2>
        {grafana ? (
          <iframe title={t("admin.grafana")} src={grafana} className="mt-2 h-96 w-full border-0" />
        ) : (
          <p className="mt-2" style={{ font: "var(--t-caption)" }}>
            {t("admin.grafanaHint")}
          </p>
        )}
      </section>
    </div>
  );
}
