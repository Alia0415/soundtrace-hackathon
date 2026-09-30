# Prototype Instructions

Product direction: preserve the dreamlike room assets and the door → memory bottles → pool → playable orb journey. Bottles represent recorded sound materials. Let users audition and carry materials, pour them with animation, and hear an output derived from their selections. Label local mixing honestly until AI generation is connected.

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
User direction (2026-09-29): emphasize a first-person viewpoint, with forward movement through the door, approaching the cabinet, turning toward the pool, and an orb rising from the water. Preserve the existing dreamlike visual assets and keep motion optional.
User direction: avoid button-card navigation. Use scene objects as interaction targets; bottles can be auditioned directly and dragged into the tray or pool. Keep small contextual hints and keyboard equivalents.
User direction: bottles should resemble dimensional glass jars with thick refractive rims, curved reflections, tiny plants and glowing stars, inspired by the supplied forest jar reference. Avoid flat icon-like bottles.
User direction: the cabinet must be a first-person spatial scene. Approach it, swing both doors outward, and persist in the open state with many bottles resting on shelves. Do not overlay bottles on a closed cabinet illustration.
User direction: retain the luminous clear-glass cabinet style from the reference, with refractive glass edges and transparent shelves. It must be a tall floor-standing cabinet with a visible base and floor contact; avoid opaque green frames.
