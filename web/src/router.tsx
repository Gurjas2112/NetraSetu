import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

export const ROUTES = ["/field", "/review", "/patient", "/admin"] as const;
export type RoutePath = (typeof ROUTES)[number];

function currentRoute(): RoutePath {
  const path = window.location.pathname.replace(/\/+$/, "");
  return (ROUTES as readonly string[]).includes(path) ? (path as RoutePath) : "/field";
}

export function navigate(to: RoutePath): void {
  if (window.location.pathname !== to) {
    window.history.pushState(null, "", to);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

export function useRoute(): RoutePath {
  const [route, setRoute] = useState<RoutePath>(currentRoute);
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
