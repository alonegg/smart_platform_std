import React from "react";
import { hydrateRoot } from "react-dom/client";
import App from "./App.jsx";
import { appPath } from "./shared.jsx";
import "./styles.css";
hydrateRoot(
  document.getElementById("root"),
  <App initialPath={appPath(location.pathname)} />,
);
