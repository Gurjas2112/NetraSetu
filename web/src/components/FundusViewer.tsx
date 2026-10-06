import OpenSeadragon from "openseadragon";
import { useEffect, useRef } from "react";
import { API_BASE, getAccessToken } from "../api/client";

type ViewerHandle = {
  destroy: () => void;
  viewport: {
    goHome: (immediately?: boolean) => void;
    zoomTo: (zoom: number, refPoint?: unknown, immediately?: boolean) => void;
    imageToViewportZoom: (imageZoom: number) => number;
  };
};

export type OverlayId = "MA" | "HE" | "EX" | "SE" | "vessels" | "gradcam";

export default function FundusViewer({
  studyId,
  gradcamUrl,
  overlays,
  oneToOne,
}: {
  studyId: string | null;
  gradcamUrl?: string | null;
  overlays: ReadonlySet<OverlayId>;
  oneToOne: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<ViewerHandle | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el || !studyId) return;
    const token = getAccessToken();
    const dzi = `${API_BASE}/study/${studyId}/tiles/image.dzi`;
    const v = OpenSeadragon({
      element: el,
      prefixUrl: "",
      showNavigationControl: false,
      visibilityRatio: 1,
      constrainDuringPan: true,
      ajaxHeaders: token ? { Authorization: `Bearer ${token}` } : {},
      loadTilesWithAjax: true,
      tileSources: dzi,
    }) as unknown as ViewerHandle;
    viewer.current = v;
    return () => {
      v.destroy();
      viewer.current = null;
    };
  }, [studyId]);

  useEffect(() => {
    const v = viewer.current;
    if (!v || !oneToOne) return;
    v.viewport.goHome(true);
    v.viewport.zoomTo(v.viewport.imageToViewportZoom(1), undefined, true);
  }, [oneToOne]);

  return (
    <div className="relative h-full min-h-[16rem] w-full" data-testid="fundus-viewer">
      <div ref={host} className="h-full w-full" />
      {overlays.has("gradcam") && gradcamUrl ? (
        <img
          src={gradcamUrl}
          alt=""
          className="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-50"
          data-testid="gradcam-overlay"
        />
      ) : null}
    </div>
  );
}
