import { useEffect } from "react";
import { Footer, Header, PreviewBar } from "./components/Chrome";
import { useRoute } from "./lib/router";
import { Checkout } from "./views/Checkout";
import { Console } from "./views/Console";
import { CoverView } from "./views/CoverView";
import { Demo } from "./views/Demo";
import { Home } from "./views/Home";
import { How } from "./views/How";
import { Log } from "./views/Log";
import { NotFound } from "./views/NotFound";
import { Vendors } from "./views/Vendors";

const TITLES: Record<string, string> = {
  home: "RedLine — Terms-backed checkout on PayPal",
  vendors: "For vendors — RedLine",
  how: "How it works — RedLine",
  demo: "Live demo — RedLine",
  checkout: "Checkout — RedLine",
  cover: "Your cover — RedLine",
  console: "Vendor console — RedLine",
  log: "Transparency log — RedLine",
  notfound: "Not found — RedLine",
};

export function App() {
  const route = useRoute();
  useEffect(() => {
    document.title = TITLES[route.name];
  }, [route]);

  let view;
  switch (route.name) {
    case "home": view = <Home />; break;
    case "vendors": view = <Vendors />; break;
    case "how": view = <How />; break;
    case "demo": view = <Demo />; break;
    case "checkout": view = <Checkout key={route.vendor} vendorToken={route.vendor} />; break;
    case "cover": view = <CoverView key={route.token} token={route.token} />; break;
    case "console": view = <Console key={route.vendor} vendorToken={route.vendor} />; break;
    case "log": view = <Log />; break;
    default: view = <NotFound />;
  }
  return (
    <>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>Skip to content</a>
      <div className="grid-lines" aria-hidden />
      <PreviewBar route={route} />
      <Header route={route} />
      {view}
      <Footer />
    </>
  );
}
