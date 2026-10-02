# Compact tokens
Inter/system sans; body 14.5px; h1 26px; h2 16px; h3 13px. Light: bg #f6f7fb, white surface, border #e3e6ef, ink #161a2b, muted #636b83, accent #5b5bf0, soft #ececff. Dark: bg #0d0f1a, surface #151827, border #272c44, ink #eceefb, muted #959cb8, accent #8a8aff. Green #12805c, blue #2563eb, amber #a15c07, rose #b42340. Radius 14px card/10px controls, sidebar 232px; spacing 6/8/10/12/14/16/18/20/28/40. Breakpoints 960px detail/profile, 760px mobile nav; subtle shadow; reduced-motion disables animation; no Tailwind.

# Raw theme

## `web/src/styles.css`
```css
:root {
  --bg: #f6f7fb; --surface: #ffffff; --surface-2: #f0f2f8; --border: #e3e6ef; --text: #161a2b; --muted: #636b83;
  --accent: #5b5bf0; --accent-ink: #ffffff; --accent-soft: #ececff;
  --great: #12805c; --great-bg: #dcf5ea; --good: #2563eb; --good-bg: #e1ecff;
  --fair: #a15c07; --fair-bg: #fdf0d5; --low: #b42340; --low-bg: #fde4e9; --none: #636b83; --none-bg: #eceef5;
  --shadow: 0 1px 2px rgb(20 24 50 / 6%), 0 8px 24px -12px rgb(20 24 50 / 14%);
  --radius: 14px; --sidebar: 232px;
  font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 14.5px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
:root[data-theme="dark"] {
  --bg: #0d0f1a; --surface: #151827; --surface-2: #1c2033; --border: #272c44; --text: #eceefb; --muted: #959cb8;
  --accent: #8a8aff; --accent-ink: #0d0f1a; --accent-soft: #23264a;
  --great: #4ade9f; --great-bg: #12372b; --good: #7aa7ff; --good-bg: #172a54;
  --fair: #f6c453; --fair-bg: #3a2c0e; --low: #ff8da1; --low-bg: #44182a; --none: #959cb8; --none-bg: #222640;
  --shadow: 0 1px 2px rgb(0 0 0 / 30%), 0 8px 24px -12px rgb(0 0 0 / 50%);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); }
button, input, select, textarea { font: inherit; color: inherit; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
h1, h2, h3 { margin: 0; letter-spacing: -0.015em; line-height: 1.2; }
h1 { font-size: 26px; } h2 { font-size: 16px; } h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 600; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }
.muted { color: var(--muted); } .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }

/* shell */
.shell { display: grid; grid-template-columns: var(--sidebar) 1fr; min-height: 100vh; }
.side { position: sticky; top: 0; height: 100vh; padding: 20px 14px; display: flex; flex-direction: column; gap: 6px; border-right: 1px solid var(--border); background: var(--surface); }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; padding: 4px 10px 18px; letter-spacing: -.02em; }
.logo { width: 30px; height: 30px; border-radius: 9px; background: linear-gradient(135deg, #6c6cff, #4343d8); display: grid; place-items: center; color: #fff; font-weight: 800; }
.nav a { display: flex; align-items: center; gap: 11px; padding: 9px 12px; border-radius: 10px; color: var(--muted); font-weight: 500; text-decoration: none; }
.nav a:hover { background: var(--surface-2); color: var(--text); }
.nav a[aria-current="page"] { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.nav svg { width: 18px; height: 18px; flex: none; }
.side-foot { margin-top: auto; display: grid; gap: 8px; font-size: 12.5px; color: var(--muted); padding: 0 6px; }
.main { padding: 28px clamp(16px, 3vw, 40px) 80px; max-width: 1280px; width: 100%; margin: 0 auto; }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
.topbar p { margin: 4px 0 0; color: var(--muted); }

/* primitives */
.btn { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--border); background: var(--surface); padding: 8px 14px; border-radius: 10px; cursor: pointer; font-weight: 500; transition: background .12s, transform .05s; }
.btn:hover { background: var(--surface-2); } .btn:active { transform: translateY(1px); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; } .btn.primary:hover { filter: brightness(1.08); background: var(--accent); }
.btn.ghost { border-color: transparent; background: transparent; } .btn.danger { color: var(--low); }
.btn:disabled { opacity: .55; cursor: progress; }
.btn svg { width: 16px; height: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); }
.card > header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; gap: 8px; }
input[type=text], input[type=search], input[type=number], input[type=url], select, textarea { width: 100%; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; }
textarea { resize: vertical; min-height: 120px; line-height: 1.45; }
input:focus, select:focus, textarea:focus { outline: 2px solid var(--accent); outline-offset: -1px; border-color: transparent; }
label.field { display: grid; gap: 6px; font-weight: 500; font-size: 13px; } label.field small { font-weight: 400; color: var(--muted); }
.chip { display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); font-size: 12.5px; white-space: nowrap; }
.chip.have { background: var(--great-bg); border-color: transparent; color: var(--great); font-weight: 500; }
.chip.miss { background: var(--low-bg); border-color: transparent; color: var(--low); font-weight: 500; }
.chip.accent { background: var(--accent-soft); color: var(--accent); border-color: transparent; font-weight: 500; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.logo-co { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; font-weight: 700; font-size: 13px; flex: none; color: #fff; }
.score { --c: var(--none); display: grid; place-items: center; position: relative; flex: none; }
.score svg { position: absolute; inset: 0; transform: rotate(-90deg); } .score b { font-size: 0.95em; letter-spacing: -.02em; }
.score[data-tone=great] { --c: var(--great); } .score[data-tone=good] { --c: var(--good); } .score[data-tone=fair] { --c: var(--fair); } .score[data-tone=low] { --c: var(--low); }
.pill { align-self: center; justify-self: start; width: fit-content; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: var(--none-bg); color: var(--none); }
.pill[data-tone=great] { background: var(--great-bg); color: var(--great); } .pill[data-tone=good] { background: var(--good-bg); color: var(--good); }
.pill[data-tone=fair] { background: var(--fair-bg); color: var(--fair); } .pill[data-tone=low] { background: var(--low-bg); color: var(--low); }
.empty { text-align: center; padding: 56px 20px; color: var(--muted); }
.empty h2 { color: var(--text); margin-bottom: 6px; }
.skeleton { background: linear-gradient(90deg, var(--surface-2), var(--border), var(--surface-2)); background-size: 200% 100%; animation: sh 1.2s infinite; border-radius: 10px; min-height: 18px; }
@keyframes sh { to { background-position: -200% 0; } }
.toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--text); color: var(--bg); padding: 11px 18px; border-radius: 12px; box-shadow: var(--shadow); z-index: 100; max-width: min(92vw, 520px); }
.toast.err { background: var(--low); color: #fff; }

/* dashboard */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 14px; }
.kpi { padding: 16px 18px; } .kpi .v { font-size: 28px; font-weight: 700; letter-spacing: -.03em; margin-top: 4px; } .kpi .s { font-size: 12.5px; color: var(--muted); }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 14px; margin-bottom: 14px; }
.bars { display: grid; gap: 9px; }
.bar { display: grid; grid-template-columns: 110px 1fr 34px; gap: 10px; align-items: center; font-size: 13px; }
.bar .track { height: 9px; border-radius: 99px; background: var(--surface-2); overflow: hidden; } .bar .fill { height: 100%; border-radius: 99px; background: var(--accent); }
.bar .fill.have { background: var(--great); } .bar .n { text-align: right; color: var(--muted); }
.funnel { display: grid; gap: 8px; }
.toplist a { display: flex; align-items: center; gap: 12px; padding: 9px 4px; border-bottom: 1px solid var(--border); color: inherit; text-decoration: none; } .toplist a:last-child { border: 0; }
.toplist a:hover { background: var(--surface-2); border-radius: 10px; } .toplist .t { flex: 1; min-width: 0; } .toplist .t div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* jobs */
.filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; } .filters > * { width: auto; } .filters input[type=search] { flex: 1; min-width: 200px; }
.jobs { display: grid; gap: 12px; }
.job { display: grid; grid-template-columns: auto 1fr auto; gap: 16px; align-items: center; padding: 16px 18px; color: inherit; text-decoration: none; transition: border-color .12s, transform .12s; }
.job:hover { border-color: var(--accent); transform: translateY(-1px); text-decoration: none; }
.job h2 { font-size: 16px; } .job .meta { display: flex; gap: 6px 14px; flex-wrap: wrap; color: var(--muted); font-size: 13px; margin: 3px 0 9px; }
.job .right { display: grid; justify-items: end; gap: 8px; }

/* detail */
.detail { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; }
.detail .stack { display: grid; gap: 14px; }
.hero { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.hero .grow { flex: 1; min-width: 220px; }
ul.clean { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; } .facts dt { font-size: 12px; color: var(--muted); } .facts dd { margin: 2px 0 0; font-weight: 500; }
.break { display: grid; gap: 10px; } .break .bar { grid-template-columns: 78px 1fr 30px; }
.timeline { display: grid; gap: 10px; font-size: 13px; } .timeline li { list-style: none; display: flex; gap: 10px; } .timeline i { width: 9px; height: 9px; border-radius: 99px; background: var(--accent); margin-top: 6px; flex: none; }
.stage-select { display: flex; flex-wrap: wrap; gap: 6px; } .stage-select button { padding: 5px 11px; font-size: 13px; border-radius: 999px; }
.stage-select button[aria-pressed=true] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }

/* pipeline */
.board { display: grid; grid-template-columns: repeat(5, minmax(220px, 1fr)); gap: 12px; overflow-x: auto; padding-bottom: 8px; align-items: start; }
.col { background: var(--surface-2); border-radius: var(--radius); padding: 10px; min-height: 240px; border: 2px dashed transparent; transition: border-color .12s, background .12s; }
.col.over { border-color: var(--accent); background: var(--accent-soft); }
.col > h3 { display: flex; justify-content: space-between; padding: 4px 6px 10px; }
.kcard { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; margin-bottom: 8px; cursor: grab; display: grid; gap: 8px; box-shadow: var(--shadow); color: inherit; text-decoration: none; }
.kcard:hover { border-color: var(--accent); text-decoration: none; } .kcard.drag { opacity: .4; } .kcard .row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.closed { margin-top: 18px; }

/* modal */
.scrim { position: fixed; inset: 0; background: rgb(8 10 22 / 55%); backdrop-filter: blur(3px); display: grid; place-items: start center; padding: 9vh 16px; z-index: 50; overflow: auto; }
.modal { width: min(640px, 100%); } .modal form { display: grid; gap: 14px; }
.tabs { display: inline-flex; background: var(--surface-2); border-radius: 10px; padding: 3px; } .tabs button { border: 0; background: none; padding: 6px 14px; border-radius: 8px; cursor: pointer; font-weight: 500; color: var(--muted); }
.tabs button[aria-selected=true] { background: var(--surface); color: var(--text); box-shadow: var(--shadow); }
.row-end { display: flex; justify-content: flex-end; gap: 10px; }
.profile { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; align-items: start; } .profile .form { display: grid; gap: 14px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

/* mobile */
.mnav { display: none; }
@media (max-width: 960px) { .detail, .profile { grid-template-columns: 1fr; } }
@media (max-width: 760px) {
  .shell { grid-template-columns: 1fr; } .side { display: none; }
  .mnav { display: grid; grid-template-columns: repeat(5, 1fr); position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface); border-top: 1px solid var(--border); z-index: 40; padding-bottom: env(safe-area-inset-bottom); }
  .mnav a { display: grid; justify-items: center; gap: 2px; padding: 8px 0; font-size: 11px; color: var(--muted); text-decoration: none; } .mnav a[aria-current=page] { color: var(--accent); } .mnav svg { width: 20px; height: 20px; }
  .main { padding-bottom: 90px; } .job { grid-template-columns: auto 1fr; } .job .right { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; }
  .board { grid-template-columns: repeat(5, 78vw); } .two, .facts { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

```
