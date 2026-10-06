import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { analyze, ApiError, giveConsent, sha256Hex, type Consent, type Study } from "../../api/client";
import DecisionBanner from "../../components/DecisionBanner";
import QualityRing from "../../components/QualityRing";
import QueueStrip from "../../components/QueueStrip";
import type { Language } from "../../i18n";
import { grayLaplacianVariance, ringScore } from "../../lib/laplacian";
import { speak } from "../../lib/speech";
import { captureFile, enqueue, pending, pendingCount, remove } from "../../offline/queue";

type Status = "idle" | "assessing" | "error";

const STAGES = ["field.stage.quality", "field.stage.disc", "field.stage.lesions", "field.stage.grade"] as const;
const MAX_RETAKES = 3;

function errorKeyFor(err: unknown): string {
  if (err instanceof ApiError && err.status === 503) return "field.error.unavailable";
  if (err instanceof ApiError && err.status === 401) return "field.error.unauthorized";
  return "field.error.generic";
}

async function scoreFile(file: File): Promise<{ url: string; score: number }> {
  const url = URL.createObjectURL(file);
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { url, score: 0 };
  ctx.drawImage(bitmap, 0, 0, 128, 128);
  const score = ringScore(grayLaplacianVariance(ctx.getImageData(0, 0, 128, 128)));
  bitmap.close();
  return { url, score };
}

export default function FieldRoute({
  study,
  onStudy,
}: {
  study: Study | null;
  onStudy: (study: Study | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language as Language;
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [patient, setPatient] = useState<Consent | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorKey, setErrorKey] = useState<string>("field.error.generic");
  const [stage, setStage] = useState(0);
  const [preview, setPreview] = useState<string | null>(null);
  const [ring, setRing] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [screened, setScreened] = useState(0);
  const [waiting, setWaiting] = useState(0);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [phone, setPhone] = useState("");
  const previewRef = useRef<string | null>(null);
  const syncing = useRef(false);

  useEffect(() => {
    void pendingCount().then(setWaiting);
  }, []);

  useEffect(() => {
    if (status !== "assessing") return;
    setStage(0);
    const id = window.setInterval(() => setStage((s) => (s + 1) % STAGES.length), 700);
    return () => window.clearInterval(id);
  }, [status]);

  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  const refreshWaiting = async () => {
    setWaiting(await pendingCount());
  };

  const flushQueue = async () => {
    if (syncing.current || !navigator.onLine) return;
    syncing.current = true;
    try {
      const items = await pending();
      let last: Study | null = null;
      for (const item of items) {
        if (item.id === undefined) continue;
        last = await analyze(captureFile(item), item.patientRef, item.consentId);
        await remove(item.id);
        setScreened((n) => n + 1);
      }
      if (items.length > 0) {
        setLastSync(new Date());
        if (last) onStudy(last);
      }
      await refreshWaiting();
    } catch {
      await refreshWaiting();
    } finally {
      syncing.current = false;
    }
  };

  const flushRef = useRef(flushQueue);
  flushRef.current = flushQueue;

  useEffect(() => {
    const onOnline = () => void flushRef.current();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  const onFile = async (next: File | null) => {
    setFile(next);
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = null;
    setPreview(null);
    setRing(0);
    if (!next) return;
    const scored = await scoreFile(next);
    previewRef.current = scored.url;
    setPreview(scored.url);
    setRing(scored.score);
  };

  const ensurePatient = async (): Promise<Consent> => {
    if (patient) return patient;
    const notice = t("field.consentNotice");
    const current = await giveConsent({
      purpose: "screening",
      noticeHash: await sha256Hex(notice),
      language,
      phone: phone.trim() ? phone.trim() : null,
    });
    setPatient(current);
    return current;
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || (!patient && !agreed)) return;
    if (attempts >= MAX_RETAKES) return;
    setStatus("assessing");
    onStudy(null);
    try {
      const current = await ensurePatient();
      const queueNow = async () => {
        await enqueue({
          createdAt: Date.now(),
          filename: file.name,
          mimeType: file.type || "image/png",
          bytes: await file.arrayBuffer(),
          patientRef: current.patientRef,
          consentId: current.consentId,
        });
        await refreshWaiting();
        setStatus("idle");
      };
      try {
        if (!navigator.onLine) {
          await queueNow();
          return;
        }
        const result = await analyze(file, current.patientRef, current.consentId);
        setScreened((n) => n + 1);
        setLastSync(new Date());
        onStudy(result);
        setStatus("idle");
        if (result.decision === "RETAKE") {
          setAttempts((n) => n + 1);
        } else {
          setAttempts(0);
        }
        const spoken = [
          t(`decision.${result.decision === "REFER" ? "refer" : result.decision === "ROUTINE" ? "routine" : "retake"}.title`),
          t(`decision.${result.decision === "REFER" ? "refer" : result.decision === "ROUTINE" ? "routine" : "retake"}.next`),
        ].join(". ");
        speak(spoken, language);
      } catch (err) {
        if (!(err instanceof ApiError)) {
          await queueNow();
          return;
        }
        throw err;
      }
    } catch (err) {
      setErrorKey(errorKeyFor(err));
      setStatus("error");
    }
  };

  const newPatient = () => {
    setPatient(null);
    setAgreed(false);
    setFile(null);
    setPhone("");
    onStudy(null);
    setStatus("idle");
    setAttempts(0);
    void onFile(null);
  };

  const blocked = attempts >= MAX_RETAKES;

  return (
    <div className="mx-auto max-w-lg">
      <h1 style={{ font: "var(--t-h1)" }}>{t("field.title")}</h1>
      <QueueStrip screened={screened} waiting={waiting} lastSync={lastSync} />

      <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
        {patient ? null : (
          <fieldset className="flex flex-col gap-2 border p-3" style={{ borderColor: "var(--nx-slate-200)" }}>
            <legend style={{ font: "var(--t-caption)" }}>{t("field.identify")}</legend>
            <p data-testid="consent-notice">{t("field.consentNotice")}</p>
            <label className="flex flex-col gap-1">
              {t("field.phone")}
              <input
                type="tel"
                autoComplete="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="border p-2"
                style={{ borderColor: "var(--nx-slate-200)" }}
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                data-testid="consent-given"
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                required
              />
              {t("field.consentGiven")}
            </label>
          </fieldset>
        )}

        <QualityRing score={ring} previewUrl={preview} />

        <label className="flex flex-col gap-1">
          {t("field.image")}
          <input
            data-testid="file-input"
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => void onFile(e.target.files?.[0] ?? null)}
            required
            disabled={blocked}
          />
        </label>

        {status === "assessing" ? (
          <p data-testid="assess-stage" role="status">
            {t(STAGES[stage] ?? STAGES[0])}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={!file || (!patient && !agreed) || status === "assessing" || blocked}
          className="p-3 disabled:opacity-50"
          style={{ background: "var(--nx-signal)", color: "var(--nx-paper)" }}
        >
          {status === "assessing" ? t("field.assessing") : t("field.submit")}
        </button>
        {patient ? (
          <button type="button" onClick={newPatient} className="p-2 underline">
            {t("field.newPatient")}
          </button>
        ) : null}
      </form>

      {blocked ? (
        <p role="alert" className="mt-4" style={{ color: "var(--dx-refer)" }}>
          {t("retake.escalate")}
        </p>
      ) : null}

      {status === "error" ? (
        <p role="alert" className="mt-4" style={{ color: "var(--dx-refer)" }}>
          {t(errorKey)}
        </p>
      ) : null}

      {study ? (
        <>
          <DecisionBanner
            decision={study.decision}
            guidanceKey={study.retakeGuidanceKey}
            attempt={study.decision === "RETAKE" ? attempts : null}
          />
          {study.criteria.length > 0 ? (
            <details>
              <summary>{t("field.why", { count: study.criteria.length })}</summary>
              <ul className="list-disc pl-6">
                {study.criteria.map((c) => (
                  <li key={c.key}>{t(c.key)}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
