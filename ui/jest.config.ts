import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  testEnvironment: "jsdom",
  testEnvironmentOptions: { customExportConditions: [""] },
  setupFiles: ["<rootDir>/src/test/msw-polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
  coverageThreshold: {
    global: { branches: 80, functions: 80, lines: 80, statements: 80 },
  },
  collectCoverageFrom: ["src/**/*.{ts,tsx}", "!src/**/*.d.ts"],
};

// next/jest prepends its own blanket "/node_modules/" ignore pattern
// and Jest OR-matches the array — our exception below never got a
// chance to fire when passed alongside `config`. Patch the merged
// result instead of the pre-merge input.
async function jestConfig() {
  const finalConfig = await createJestConfig(config)();
  finalConfig.transformIgnorePatterns = [
    "node_modules/(?!.*(msw|mswjs|rettime|until-async|@open-draft|strict-event-emitter|headers-polyfill|outvariant))",
  ];
  return finalConfig;
}

export default jestConfig;
