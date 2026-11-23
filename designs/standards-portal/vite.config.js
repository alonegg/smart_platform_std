import { defineConfig } from "vite";
import { basePath, isR2 } from "./scripts/edition.mjs";
import { r2Aliases } from "./scripts/r2-aliases.mjs";
export default defineConfig({
  base: basePath,
  ...(isR2 ? { resolve: { alias: Object.entries(r2Aliases).map(([find, replacement]) => ({ find, replacement })) } } : {}),
  build: {
    sourcemap: false,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "react-vendor", test: /node_modules/ },
            { name: "standard-content", test: /generated\.json/ },
          ],
        },
      },
    },
  },
});
