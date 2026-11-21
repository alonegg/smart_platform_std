import { fileURLToPath } from "node:url";
import { isPublicR2 } from "./edition.mjs";

const names = ["Consultation", "registration", "Topics"];
if (!isPublicR2) names.push("App");
export const r2Aliases = Object.fromEntries(names.map((name) => [
  `./${name}.jsx`, fileURLToPath(new URL(`../src/r2/${name}.jsx`, import.meta.url)),
]));
