import * as React from "react";
import { createRoot } from "react-dom/client";
import App from "./app";

declare const __SLAPDASH_VERSION__: string; // injected by build.mjs

let api = document.location.href;
if (process.env.NODE_ENV === "development") {
  api = "http://localhost:8000";
  console.log("development");
  console.log(__SLAPDASH_VERSION__);
}

createRoot(document.getElementById("root")).render(<App api={api} />);
