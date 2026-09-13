// ui/jest.config.ts
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
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
    // DOM/audio/canvas/native-DnD surfaces PRD already scoped out of
    // the test surface (locked "logic-only tests" decision, FE7-4/
    // FE7-6/FE7-7) — pure logic extracted from each is tested
    // separately (player-reducer.ts, shuffle.ts, waveform.ts,
    // reorder.ts). Counting these in coverage would force DOM tests
    // the PRD explicitly decided against, not close a real gap.
    "!src/components/PlayerProvider.tsx",
    "!src/components/PlayerBar.tsx",
    "!src/components/NowPlayingPanel.tsx",
    "!src/lib/waveform-cache.ts",
    "!src/app/playlists/[id]/PlaylistDetailClient.tsx",
    // Composition-root shells: layout.tsx just mounts providers (no
    // branch logic of its own — PlayerProvider/ToastProvider are
    // tested separately), playlists/[id]/page.tsx is only
    // generateStaticParams() (build-time only, can't run under Jest).
    "!src/app/layout.tsx",
    "!src/app/playlists/[id]/page.tsx",
    "!src/test/**",
  ],
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
