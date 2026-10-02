# Jobbr design system
Jobbr helps capture postings, explain fit, track application stages and improve a resume/profile. React + Vite hash routes overview/jobs/detail/pipeline/profile. JTBD: decide which role deserves attention today, take the next action.

## Current reproduction
Follow web/src/styles.css exactly. Inter/system sans, #f6f7fb bg, white cards, #161a2b ink, #636b83 muted, #5b5bf0 action, #ececff soft. 232px sidebar; 14px cards; 10px controls. Preserve actual source composition.

## Authorized redesign: professional command center
One coherent design: Inter/system sans only; white/#f6f7fb/#f0f2f8 surfaces; #161a2b ink; restrained #5b5bf0 accent. No decorative type/neon/page gradients/stock imagery. Render real provided purple Jobbr logo. Green #12805c success, blue #2563eb active, amber #a15c07 attention, rose #b42340 gaps. Existing dark tokens allowed for dark mode. Type 12/13/14.5/16/18/26/34/40px; weights 400/500/600/700. Spacing 4/6/8/10/12/14/16/18/20/24/28/32/40/48; corners 8/10/12/14/18px. Subtle existing shadow. 44px control targets.

Desktop: sidebar + compact top workspace bar; personal greeting/next-best-action; compact metrics; rich best-match list; focused next-actions/coach rail; compact pipeline. Prioritize role, company, location/remote, salary, explainable fit, stage, action. Fit is a heuristic, never a hiring probability. Coach turns detected skill gaps into practical next steps. No promises or invented telemetry. Mock values must be sample content.

Responsive at 760px: hide sidebar; bottom nav; stack cards; avoid global overflow. Keyboard focus, semantic buttons/links, labeled search, accessible score text, text with status color. Reduced-motion respected; only 120–200ms transitions. Recoverable empty/error/read-only states. Proposed new features must remain documented as design concepts until backed by implementation.
