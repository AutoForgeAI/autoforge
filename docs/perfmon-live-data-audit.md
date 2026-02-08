# PerfMon Live-Data Audit

Date: 2026-02-08
Scope: Read-only audit of current PerfMon implementation and minimal path to live telemetry.

## 1) Current PerfMon Rendering And Toggle

- PerfMon is mounted in the top header controls in `ui/src/App.tsx:369` as `<PerfMonPanel isLive={isAgentLive} />`.
- The header is sticky and high stacking context (`ui/src/App.tsx:265`), with a shared tooltip provider wrapping controls (`ui/src/App.tsx:267`, `ui/src/App.tsx:394`).
- `isAgentLive` is derived from websocket agent state in `ui/src/App.tsx:87`:
  - `wsState.agentStatus === 'running' || wsState.agentStatus === 'paused'`
- The panel open state is local in `ui/src/components/PerfMonPanel.tsx:25`.
- Open/close behavior:
  - Button toggles state (`ui/src/components/PerfMonPanel.tsx:58`)
  - Outside click closes (`ui/src/components/PerfMonPanel.tsx:32`)
  - `Escape` closes (`ui/src/components/PerfMonPanel.tsx:38`)
- Panel mount behavior:
  - Not portaled; rendered as absolute element under button (`ui/src/components/PerfMonPanel.tsx:80`)
  - Uses `z-40` inside header context.
- Tooltip behavior:
  - PerfMon button uses Radix tooltip (`ui/src/components/PerfMonPanel.tsx:69`)
  - Tooltip content is portaled in shared wrapper (`ui/src/components/ui/tooltip.tsx:42`, `ui/src/components/ui/tooltip.tsx:44`).

## 2) Current Data Flow

### `usePerfMonMock` shape and cadence

`ui/src/hooks/usePerfMonMock.ts` returns:

- `tokens`
  - `currentRun`
  - `totalSession`
  - `usagePercent`
- `cpu`
  - `percent`
- `memory`
  - `used`
  - `total`
  - `percent`
- `gpu`
  - `available`
  - `percent`
  - `used`
  - `total`

Generation model:

- Deterministic smooth wave + clamp (`const wave`, `const clamp`) in `ui/src/hooks/usePerfMonMock.ts:3`, `ui/src/hooks/usePerfMonMock.ts:6`.
- No random noise spikes.
- GPU availability flips periodically (`ui/src/hooks/usePerfMonMock.ts:53`).

Update cadence:

- `1s` while running, `3s` while idle (`ui/src/hooks/usePerfMonMock.ts:85`).
- Interval-based updates (`ui/src/hooks/usePerfMonMock.ts:94`).

### PerfMonPanel consumption

- `PerfMonPanel` consumes `usePerfMonMock(isLive)` directly (`ui/src/components/PerfMonPanel.tsx:27`).
- `isLive` affects:
  - mock update rate (through hook)
  - button/panel badge variant and label (`Live`/`Idle`) (`ui/src/components/PerfMonPanel.tsx:72`, `ui/src/components/PerfMonPanel.tsx:83`).

Assumption:

- “Agent running” is inferred only from websocket `agentStatus` in `App`.

## 3) Existing Live Sources In Repo

### WebSocket channel already used in app

- Client hook: `useProjectWebSocket(projectName)` in `ui/src/hooks/useWebSocket.ts:61`.
- Connects to `/ws/projects/{project_name}` (`ui/src/hooks/useWebSocket.ts:88`).
- Current state already tracked in UI hook:
  - `progress`, `agentStatus`, `isConnected`, `activeAgents`, `orchestratorStatus`, `devServerStatus` (`ui/src/hooks/useWebSocket.ts:33`, `ui/src/hooks/useWebSocket.ts:39`, `ui/src/hooks/useWebSocket.ts:41`, `ui/src/hooks/useWebSocket.ts:46`, `ui/src/hooks/useWebSocket.ts:54`).
- Message handlers exist for:
  - `progress` (`ui/src/hooks/useWebSocket.ts:104`)
  - `agent_status` (`ui/src/hooks/useWebSocket.ts:116`)
  - `orchestrator_update` (`ui/src/hooks/useWebSocket.ts:284`)
  - `dev_server_status` (`ui/src/hooks/useWebSocket.ts:321`)

### Backend websocket wiring

- WebSocket endpoint in `server/main.py:167`, delegated to `project_websocket` (`server/main.py:170`).
- Handler in `server/websocket.py:719`.
- Existing push sources:
  - progress polling task (`server/websocket.py:685`, `server/websocket.py:843`)
  - agent output callback (`server/websocket.py:758`, registered at `server/websocket.py:810`)
  - agent status callback (`server/websocket.py:795`, registered at `server/websocket.py:811`)
  - dev server status callback (`server/websocket.py:827`, registered at `server/websocket.py:840`)

### REST status endpoints and polling patterns

- Agent status endpoint:
  - UI call `getAgentStatus` at `ui/src/lib/api.ts:232`
  - Backend route `server/routers/agent.py:70`
  - Polling hook every 3s at `ui/src/hooks/useProjects.ts:140`, `ui/src/hooks/useProjects.ts:145`
- Features polling every 5s at `ui/src/hooks/useProjects.ts:82`, `ui/src/hooks/useProjects.ts:87`
- Project stats endpoint exists (`/stats`) for pass/in-progress totals only (`server/routers/projects.py:367`).

### Current WS contract does not include perf metrics

- `WSMessageType` and `WSMessage` in `ui/src/lib/types.ts:243`, `ui/src/lib/types.ts:318` do not include perf telemetry fields.

## 4) Minimal Live-Data Integration Plan

### Preferred transport

- Prefer existing project WebSocket path over new polling endpoint.
- Reason:
  - Current page already keeps one WS open.
  - Existing architecture already emits multiple live message types over this channel.
  - Lower surface area than adding new endpoint + polling hook + cache invalidation path.

### Proposed API contract

Message type: `perf_metrics`

```json
{
  "type": "perf_metrics",
  "timestamp": "2026-02-08T20:15:30.123Z",
  "project": "my-project",
  "run": {
    "status": "running",
    "pid": 12345,
    "started_at": "2026-02-08T20:10:00Z",
    "run_id": "12345-2026-02-08T20:10:00Z"
  },
  "tokens": {
    "current_run": 1420,
    "total_session": 9180,
    "available": false
  },
  "cpu": {
    "percent": 37.2
  },
  "memory": {
    "used_gb": 6.2,
    "total_gb": 16.0,
    "percent": 38.8
  },
  "gpu": {
    "available": false,
    "percent": null,
    "vram_used_gb": null,
    "vram_total_gb": null
  }
}
```

### Error/empty states and dev fallback

- UI behavior:
  - If no live payload yet, show empty placeholders (`Not available`) without errors.
  - If stale payload (e.g. >10s old), mark as stale and dim values.
- Dev fallback to mock only:
  - `import.meta.env.DEV && import.meta.env.VITE_PERFMON_MOCK !== '0'`
  - Use mock when live payload absent or disabled by backend.
- Production:
  - No automatic fake fallback; show unavailable states instead.

## 5) Risks / Maintainer Concerns

### Security

- Host-level metrics may expose machine characteristics.
- In remote mode (`AUTOFORGE_ALLOW_REMOTE` in `server/main.py:97`), exposure risk is higher.
- Keep payload coarse and project-scoped, avoid file paths/usernames/process cmdline leakage.
- Ensure project-name validation and existing WS auth/path checks remain the gate.

### Performance

- Target 1s updates while running, 3s when idle to match current UI cadence expectations.
- Avoid rerender churn:
  - do not update PerfMon state if values change minimally
  - optionally pause updates when panel is closed (or keep lower-frequency store updates).

### Cross-platform

- CPU/memory are feasible with existing server dependency `psutil`.
- GPU/VRAM portability is inconsistent across OS/vendors.
- Contract should support `gpu.available=false` and null GPU values.

## 6) Implementation Checklist (5-8 Small Steps)

1. Add perf telemetry message types to shared UI contracts in `ui/src/lib/types.ts` (`WSPerfMetricsMessage`, union update).
2. Extend websocket UI state in `ui/src/hooks/useWebSocket.ts` with `perfMetrics` and add `case 'perf_metrics'`.
3. Add backend schema class(es) in `server/schemas.py` for perf payload (optional but recommended for contract clarity).
4. In `server/websocket.py`, add a lightweight perf sampling loop inside `project_websocket` that emits `perf_metrics` at 1s/3s cadence.
5. Source initial live fields from existing manager state:
   - `status`, `pid`, `started_at` from process manager already used in `server/routers/agent.py:78`.
   - CPU/memory from `psutil`.
   - GPU optional/null when unavailable.
6. Update `ui/src/components/PerfMonPanel.tsx` to consume live metrics from WS first, with mock fallback in dev only.
7. Add UI stale/unavailable states and keep existing `Live`/`Idle` badge behavior.
8. Add a focused test for panel rendering with telemetry payload shape (or hook-level test), without adding a new test framework.

## Recommended Next PR Scope

Preferred scope: **add server websocket perf message + UI wiring** in one small PR.

Rationale:

- Delivers true live data immediately.
- Reuses established transport and state patterns already central to this screen.
- Keeps diff localized to websocket contract + PerfMon consumption code, avoiding new endpoint and polling complexity.
