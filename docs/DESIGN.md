# Jobbr frontend design

Status: Superdesign prototype complete; frontend implementation authorized by the user’s “please resume all work” instruction following the concrete prototype review.

Canvas: https://superdesign.dev/teams/daa6c1df-346f-4dc3-81dd-fb4f462aff90/projects/7b6925d7-25f7-4674-bcde-a2a59cf8354e

The proposed direction is a job search command center. It builds on working job capture, profile-based fit scoring, search/filtering, role detail, and application stages. The overview will prioritize strong opportunities and concrete next steps with a coach rail that connects detected skill gaps to resume/profile work. New scheduling, notifications, automated application, or generated application materials are concepts unless their backend support is separately implemented and verified.

The foundation is the current Inter/system sans typography, purple primary accent, quiet neutral surfaces, meaningful fit/status colors, and the canonical `web/public/favicon.svg` logo. Navigation remains Overview, Jobs, Pipeline, and Profile. Desktop uses a persistent sidebar; mobile stacks content above a bottom navigation. Focus indicators, readable text scores, labeled controls, and reduced motion are required.

The selected context sent to Superdesign is limited to six deliberate UI files: `.superdesign/design-system.md`, `web/src/App.tsx`, `web/src/pages/Dashboard.tsx`, `web/src/ui.tsx`, `web/src/util.ts`, and `web/src/styles.css`; the only uploaded visual asset is the public logo. No backend source, actual profile/resume, secrets, datasets, or credentials are included. Draft values are sample content.

The current populated Overview baseline is reproduced from source before redesigning. Source-based reproduction is a design artifact, not a claim of screenshot-perfect browser verification. User canvas review determines approval. Durable project/draft IDs, hashes, context and versions are maintained in `.superdesign/resume.json` after each successful result.

## Review links and verification

- Current UI baseline: https://p.superdesign.dev/draft/b6b00f85-0e6e-4c1a-bb5a-e7a53c0ad599
- Proposed command center (version 3): https://p.superdesign.dev/draft/58530471-d5ac-47ce-a7ce-d2e12986540d
- Generation used 13 credits total (6 baseline, 7 redesign); direct corrections used no generation credits.

The generated draft was refetched for HTML inspection. The exact canonical logo URL is visibly present in its image markup. Direct version-2 repairs make viewport responsive, label search/navigation, add focus and reduced-motion rules, add mobile bottom clearance and descriptive prototype links, and remove unsupported notification/sync/subscription-plan copy. These are structural checks; rendering and full accessibility require review on the canvas and browser checks during implementation. Navigation destinations are prototype route placeholders, not generated sibling screens.

Approval gate: `/mnt/c/Users/jkail/.agents/skills/superdesign/references/SUPERDESIGN.md` states “only implement actual code AFTER user approve OR the user explicitly says 'skip design and implement'.” The next step is approval of this concrete canvas direction before replacing frontend code.

Version 3 removes unsupported response-rate/fit-improvement claims and invented personal interview/project details. Recommendations now ask the user to review real requirements, add supported experience and prepare relevant examples. The Sample Data Overview badge remains. Same draft ID and preview link; direct copy correction used no generation credits.

## Implemented command center

The reviewed version-3 direction now has a React implementation in `web/src/components/AppShell.tsx`, `web/src/pages/Dashboard.tsx` and shared `ui.tsx`/`styles.css`. The shell uses the locally hosted canonical logo, accessible mobile navigation, a skip link, theme controls and an authorized quick-search dialog with Cmd/Ctrl K. Search remains disabled and unmounted before access is allowed. Shared dialogs trap keyboard focus, return focus to the opener, close with Escape and lock background scrolling.

The overview reads actual stats, saved jobs, profile and instance config. Strong matches are open roles with fit at least 80; scheduled focus steps come only from saved `next_step_at` data. Recommendations link to actual role details or profile edits. Career compass uses observed skill-demand counts and says “not detected,” never assumes the user lacks experience. Profile progress describes four explicit essentials rather than an invented readiness score. Demo disclosure uses the server’s `seed_demo` setting. No unknown AI spend is presented as free. New discovery, PDF import, career drafting and access controls share the same light/dark styles and mobile layout.

Frontend lint, type checking and production build passed with `npm --prefix web run check`. Parent agent owns browser rendering and interaction verification; no visual QA is claimed from source checks. The canvas draft remains version 3; implementation does not spend more design credits. Original canvas context fingerprints are preserved as a baseline, so subsequent design work detects and refreshes the changed implementation context instead of silently treating old code as current.
