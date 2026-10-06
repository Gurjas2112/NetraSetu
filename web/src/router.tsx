import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

export const ROUTES = ["/field", "/review", "/patient", "/admin"] as const;
export type RoutePath = (typeof ROUTES)[number];

export type RouteState = { path: RoutePath; patientToken: string | null };

function currentRoute(): RouteState {
  const raw = window.location.pathname.replace(/\/+$/, "") || "/field";
  const patient = /^\/patient\/([^/]+)$/.exec(raw);
  if (patient?.[1]) return { path: "/patient", patientToken: patient[1] };
  if ((ROUTES as readonly string[]).includes(raw)) {
    return { path: raw as RoutePath, patientToken: null };
  }
  return { path: "/field", patientToken: null };
}

export function navigate(to: string): void {
  if (window.location.pathname !== to) {
    window.history.pushState(null, "", to);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

export function useRoute(): RouteState {
  const [route, setRoute] = useState<RouteState>(currentRoute);
  useEffect(() => {
    const onPop = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return route;
}

export function Link({ to, children }: { to: RoutePath; children: ReactNode }) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} onClick={onClick} className="underline-offset-4 hover:underline">
      {children}
    </a>
  );
}
