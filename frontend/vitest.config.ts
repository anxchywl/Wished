import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  oxc: {
    jsx: {
      runtime: "automatic",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["../tests/frontend/**/*.test.{ts,tsx}"],
    setupFiles: [path.resolve(__dirname, "../tests/frontend/setup.ts")],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@testing-library/jest-dom": path.resolve(
        __dirname,
        "./node_modules/@testing-library/jest-dom/dist/index.mjs",
      ),
      "@testing-library/react": path.resolve(
        __dirname,
        "./node_modules/@testing-library/react/dist/index.js",
      ),
      "react/jsx-dev-runtime": path.resolve(
        __dirname,
        "./node_modules/react/jsx-dev-runtime.js",
      ),
      "react/jsx-runtime": path.resolve(__dirname, "./node_modules/react/jsx-runtime.js"),
      react: path.resolve(__dirname, "./node_modules/react/index.js"),
      "react-dom": path.resolve(__dirname, "./node_modules/react-dom/index.js"),
    },
  },
  server: {
    fs: {
      allow: [path.resolve(__dirname, "..")],
    },
  },
});
