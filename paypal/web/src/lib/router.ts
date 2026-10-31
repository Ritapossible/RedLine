// Hash routes: the app is static files, so any host serves it and links
// survive a reload.
import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "vendors" }
  | { name: "how" }
  | { name: "demo" }
  | { name: "checkout"; vendor: string }
  | { name: "cover"; token: string }
  | { name: "console"; vendor: string }
  | { name: "log" }
  | { name: "notfound" };

export function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [head, arg] = parts;
  switch (head ?? "") {
    case "":
      return { name: "home" };
    case "vendors":
      return { name: "vendors" };
    case "how":
      return { name: "how" };
    case "demo":
      return { name: "demo" };
    case "log":
      return { name: "log" };
    case "checkout":
      return arg ? { name: "checkout", vendor: arg } : { name: "demo" };
    case "cover":
      return arg ? { name: "cover", token: arg } : { name: "notfound" };
    case "console":
      return arg ? { name: "console", vendor: arg } : { name: "demo" };
    default:
      return { name: "notfound" };
  }
}

export function href(r: Route): string {
  switch (r.name) {
    case "home":
      return "#/";
    case "checkout":
      return `#/checkout/${r.vendor}`;
    case "cover":
      return `#/cover/${r.token}`;
    case "console":
      return `#/console/${r.vendor}`;
    default:
      return `#/${r.name}`;
  }
}

export function go(r: Route) {
  window.location.hash = href(r);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
