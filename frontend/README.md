# GreenThumb web UI

React + Vite single-page app. It is the control surface for the planter: zone
moisture and watering, gantry jogging, lighting, history charts and settings.
It talks to the FastAPI backend under `/api/v1`.

## Layout

- `src/App.jsx` — tab shell and shared state
- `src/components/TopBar.jsx` — header and connection status
- `src/components/TabBar.jsx` — tab switching
- `src/components/GeneralPanel.jsx` — status overview
- `src/components/PlantsPanel.jsx` — per-zone moisture, targets and manual watering
- `src/components/GantryPanel.jsx` — homing and jogging
- `src/components/HistoryPanel.jsx` + `Chart.jsx` — history charts
- `src/components/LogsPanel.jsx` — recent log lines

## Local development

```bash
npm install
npm run dev
```

`vite.config.js` proxies `/api` to `http://localhost:8000`, so run the backend on
the same machine. To develop against the Pi instead, point that proxy target at
`http://greenthumb.local:8000`.

## Build output is not committed

`npm run build` writes `dist/`, which is gitignored. On the Pi, nginx serves
`/opt/greenthumb/frontend/dist` and
[deploy/pi/install-green-thumb.sh](../deploy/pi/install-green-thumb.sh) builds it
during the install.

It used to be committed, which meant every install on the Pi rewrote tracked
files and left the checkout dirty, so the next `git pull` refused to merge. Build
output belongs to the machine that serves it.

**So a frontend change needs a build on the Pi, not just a `git pull`** — re-run
the install script, or `cd /opt/greenthumb/frontend && npm run build`.

## Lockfile

`npm install` on the Pi rewrites `package-lock.json`, because the committed
lockfile is generated on Windows and lacks the ARM Rollup binary. The install
script checks the file back out afterwards so the churn does not dirty the
checkout. That is also why it uses `npm install` rather than `npm ci`.
