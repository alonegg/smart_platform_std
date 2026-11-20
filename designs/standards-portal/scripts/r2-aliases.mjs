import { fileURLToPath } from "node:url";
export const r2Aliases = Object.fromEntries(["App", "Consultation", "registration", "Topics"].map((name) => [
  `./${name}.jsx`, fileURLToPath(new URL(`../src/r2/${name}.jsx`, import.meta.url)),
]));
