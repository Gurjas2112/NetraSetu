import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  fetchReviewQueue,
  getStudy,
  signReview,
  type ReviewQueueItem,
  type Study,
} from "../../api/client";
import EvidenceStrip from "../../components/EvidenceStrip";
import FundusViewer, { type OverlayId } from "../../components/FundusViewer";
import PosteriorBand from "../../components/PosteriorBand";

const OVERLAY_BY_KEY: Record<string, OverlayId> = {
  "1": "MA",
  "2": "HE",
  "3": "EX",
  "4": "SE",
  "5": "vessels",
};

const REASONS = ["image_artefact", "lesion_miscount", "disc_region_confusion", "dme_missed"] as const;

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const a = sorted[mid];
  if (a === undefined) return null;
  if (sorted.length % 2 === 1) return a;
  const b = sorted[mid - 1];
  if (b === undefined) return a;
  return (a + b) / 2;
}

export default function ReviewRoute({ study }: { study: Study | null }) {
  const { t } = useTranslation();
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [current, setCurrent] = useState<Study | null>(study);
  const [index, setIndex] = useState(0);
  const [overlays, setOverlays] = useState<Set<OverlayId>>(new Set());
  const [oneToOne, setOneToOne] = useState(false);
  const [picking, setPicking] = useState(false);
  const [signed, setSigned] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startedAt] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [completed, setCompleted] = useState<number[]>([]);

  useEffect(() => {
    setCurrent(study);
  }, [study]);

  useEffect(() => {
    const id = window.setInterval(() => setElapsed(Date.now() - startedAt), 250);
    return () => window.clearInterval(id);
  }, [startedAt]);

  useEffect(() => {
    let cancelled = false;
    fetchReviewQueue()
      .then((items) => {
        if (!cancelled) setQueue(items);
      })
      .catch(() => {
        /* screener tokens cannot list the queue; the in-memory study still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadFromQueue = useCallback(
    async (i: number) => {
      const item = queue[i];
      if (!item) return;
      try {
        setCurrent(await getStudy(item.studyId));
        setIndex(i);
        setSigned(null);
        setPicking(false);
        setOneToOne(false);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("review.error"));
      }
    },
    [queue, t],
  );

  const shown = current;
  const med = useMemo(() => median(completed), [completed]);

  const finish = useCallback(
    async (decision: Study["decision"], grade: number | null, reasonChip: (typeof REASONS)[number] | null) => {
      if (!shown) return;
      const elapsedMs = Date.now() - startedAt;
      try {
        await signReview(shown.studyId, { decision, grade, reasonChip, elapsedMs });
      } catch (err) {
        if (!(err instanceof ApiError && (err.status === 403 || err.status === 401))) {
          setError(err instanceof ApiError ? err.message : t("review.error"));
          return;
        }
      }
      setCompleted((xs) => [...xs, elapsedMs]);
      setSigned(decision);
      setPicking(false);
    },
    [shown, startedAt, t],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      const key = event.key;
      if (key === "j" || key === "J") {
        event.preventDefault();
        void loadFromQueue(Math.min(index + 1, Math.max(queue.length - 1, 0)));
      } else if (key === "k" || key === "K") {
        event.preventDefault();
        void loadFromQueue(Math.max(index - 1, 0));
      } else if (key === "a" || key === "A") {
        event.preventDefault();
        if (shown) void finish(shown.decision, shown.grade, null);
      } else if (key === "o" || key === "O") {
        event.preventDefault();
        setPicking(true);
      } else if (key === "u" || key === "U") {
        event.preventDefault();
        void finish("RETAKE", null, "image_artefact");
      } else if (key === "g" || key === "G") {
        event.preventDefault();
        setOverlays((prev) => {
          const next = new Set(prev);
          if (next.has("gradcam")) next.delete("gradcam");
          else next.add("gradcam");
          return next;
        });
      } else if (key === "z" || key === "Z") {
        event.preventDefault();
        setOneToOne((z) => !z);
      } else {
        const overlay = OVERLAY_BY_KEY[key];
        if (overlay) {
          event.preventDefault();
          setOverlays((prev) => {
            const next = new Set(prev);
            if (next.has(overlay)) next.delete(overlay);
            else next.add(overlay);
            return next;
          });
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finish, index, loadFromQueue, queue.length, shown]);

  const onLogoutTiles = async () => {
    if (typeof caches !== "undefined") await caches.delete("tiles");
  };

  return (
    <div
      className="flex h-[calc(100vh-4.5rem)] flex-col overflow-hidden"
      style={{ background: "var(--nx-void)", color: "var(--nx-paper)" }}
      data-testid="review-console"
    >
      <div className="flex items-center justify-between gap-3 px-3 py-2" style={{ font: "var(--t-caption)" }}>
        <span>
          {t("review.caseOf", { n: index + 1, total: Math.max(queue.length, shown ? 1 : 0) })}
        </span>
        <span data-testid="review-timer" style={{ font: "var(--t-data)", fontVariantNumeric: "tabular-nums" }}>
          {(elapsed / 1000).toFixed(0)}s
          {med !== null ? ` · ${t("review.median", { s: (med / 1000).toFixed(0) })}` : ""}
        </span>
        <button type="button" onClick={() => void onLogoutTiles()} className="underline">
          {t("review.clearTiles")}
        </button>
      </div>

      {!shown ? (
        <p className="p-6">{t("review.empty")}</p>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden p-3 lg:grid-cols-[3fr_2fr]">
          <FundusViewer
            studyId={shown.studyId}
            gradcamUrl={shown.gradcamUrl}
            overlays={overlays}
            oneToOne={oneToOne}
          />
          <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
            <p style={{ font: "var(--t-h1)" }}>{shown.grade === null ? t("review.none") : t(`grade.${shown.grade}`)}</p>
            <p data-testid="review-decision">{shown.decision}</p>
            <PosteriorBand posterior={shown.posterior} />
            <EvidenceStrip evidence={shown.evidence} />
            <p style={{ font: "var(--t-caption)" }}>{t("review.keys")}</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" data-testid="review-agree" onClick={() => void finish(shown.decision, shown.grade, null)}>
                {t("review.agree")}
              </button>
              <button type="button" data-testid="review-overturn" onClick={() => setPicking(true)}>
                {t("review.overturn")}
              </button>
              <button type="button" data-testid="review-ungradeable" onClick={() => void finish("RETAKE", null, "image_artefact")}>
                {t("review.ungradeable")}
              </button>
            </div>
            {picking ? (
              <div data-testid="reason-chips" className="flex flex-wrap gap-2">
                {REASONS.map((reason) => (
                  <button
                    key={reason}
                    type="button"
                    data-testid={`reason-${reason}`}
                    onClick={() => void finish(shown.decision === "REFER" ? "ROUTINE" : "REFER", shown.decision === "REFER" ? 1 : 2, reason)}
                  >
                    {t(`review.reason.${reason}`)}
                  </button>
                ))}
              </div>
            ) : null}
            {signed ? (
              <p data-testid="review-signed">{t("review.signed", { decision: signed })}</p>
            ) : null}
            {error ? (
              <p role="alert">{error}</p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
