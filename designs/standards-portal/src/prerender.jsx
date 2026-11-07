import React from "react";
import { renderToString } from "react-dom/server";
import App, { routes } from "./App.jsx";
export { routes };
export const render = (initialPath) =>
  renderToString(<App initialPath={initialPath} />);
