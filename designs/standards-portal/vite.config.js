import { defineConfig } from "vite";
export default defineConfig({
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
