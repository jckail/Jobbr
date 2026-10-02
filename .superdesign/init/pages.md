# Page dependency trees
Shell: main.tsx → App.tsx → ui.tsx/api.ts and route page. Global: styles.css.

## /
- `web/src/pages/Dashboard.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/types.ts` (already traced)
  - `web/src/types.ts` (already traced)
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
  - `web/src/util.ts` (already traced)

## /jobs
- `web/src/pages/Jobs.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
  - `web/src/util.ts` (already traced)

## /jobs/:id
- `web/src/pages/JobDetail.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/types.ts` (already traced)
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
  - `web/src/util.ts` (already traced)

## /pipeline
- `web/src/pages/Pipeline.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/types.ts` (already traced)
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
  - `web/src/util.ts` (already traced)

## /profile
- `web/src/pages/ProfilePage.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/types.ts` (already traced)
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
  - `web/src/util.ts` (already traced)

## AddJob
- `web/src/pages/AddJob.tsx`
  - `web/src/api.ts`
    - `web/src/types.ts`
  - `web/src/ui.tsx`
    - `web/src/api.ts` (already traced)
    - `web/src/util.ts`
