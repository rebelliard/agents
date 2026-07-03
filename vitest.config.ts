import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    exclude: ["dist/**", "node_modules/**"],
    include: ["src/**/*.{test,spec}.?(c|m)[jt]s?(x)"],
    restoreMocks: true,
  },
});
