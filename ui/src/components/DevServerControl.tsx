import { useMemo, useState } from 'react'
import { ExternalLink, Play, Square, Trash2 } from 'lucide-react'
import { startDevServer, stopDevServer } from '../lib/api'
import { useDevServerWebSocket } from '../hooks/useDevServerWebSocket'

export function DevServerControl({ projectName }: { projectName: string }) {
  const {
    status,
    pid,
    started_at,
    command,
    url,
    logs,
    isConnected,
    clearLogs,
  } = useDevServerWebSocket(projectName)

  const [commandOverride, setCommandOverride] = useState('')
  const [busy, setBusy] = useState(false)
  const statusLabel = useMemo(() => {
    if (status === 'running') return 'RUNNING'
    if (status === 'crashed') return 'CRASHED'
    return 'STOPPED'
  }, [status])

  const start = async () => {
    setBusy(true)
    try {
      await startDevServer(projectName, {
        command: commandOverride.trim() ? commandOverride.trim() : null,
      })
    } finally {
      setBusy(false)
    }
  }

  const stop = async () => {
    setBusy(true)
    try {
      await stopDevServer(projectName)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-1 text-xs font-mono border-2 border-black ${
                status === 'running'
                  ? 'bg-[var(--color-neo-progress)] text-black'
                  : status === 'crashed'
                    ? 'bg-red-500 text-white'
                    : 'bg-white text-black'
              }`}
            >
              {statusLabel}
            </span>
            <span className="text-xs font-mono text-gray-400">
              {isConnected ? 'WS: connected' : 'WS: disconnected'}
            </span>
          </div>
          <div className="mt-1 text-xs text-gray-300 font-mono break-all">
            {command ? (
              <>
                <span className="text-gray-500">cmd:</span> {command}
              </>
            ) : (
              <span className="text-gray-500">No command (stopped)</span>
            )}
          </div>
          {pid && (
            <div className="text-xs text-gray-500 font-mono">
              pid: {pid}
              {started_at ? ` • started: ${new Date(started_at).toLocaleTimeString()}` : ''}
            </div>
          )}
          {url && (
            <div className="mt-1 flex items-center gap-2 min-w-0">
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-mono text-cyan-300 hover:underline break-all"
                title={url}
              >
                {url}
              </a>
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="neo-btn text-xs bg-white text-black flex items-center gap-1"
                title="Open"
              >
                <ExternalLink size={14} />
                <span className="hidden sm:inline">Open</span>
              </a>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {status !== 'running' ? (
            <button
              className="neo-btn text-xs bg-[var(--color-neo-accent)] text-white flex items-center gap-1"
              onClick={start}
              disabled={busy}
              title="Start dev server"
            >
              <Play size={14} />
              Start
            </button>
          ) : (
            <button
              className="neo-btn text-xs bg-white text-black flex items-center gap-1"
              onClick={stop}
              disabled={busy}
              title="Stop dev server"
            >
              <Square size={14} />
              Stop
            </button>
          )}
          <button
            className="neo-btn text-xs bg-[#333] text-white flex items-center gap-1"
            onClick={(e) => {
              e.preventDefault()
              clearLogs()
            }}
            title="Clear dev server logs"
          >
            <Trash2 size={14} />
            Clear
          </button>
        </div>
      </div>

      {status !== 'running' && (
        <div className="neo-card p-3 bg-[#111] border border-[#333]">
          <div className="text-xs font-mono text-gray-400 mb-2">
            Command override (optional). Leave empty to auto-detect from `autocoder.yaml` or `package.json`.
          </div>
          <input
            className="w-full px-3 py-2 text-sm font-mono bg-[#1a1a1a] text-white border border-[#333] rounded"
            placeholder="e.g. npm run dev"
            value={commandOverride}
            onChange={(e) => setCommandOverride(e.target.value)}
          />
        </div>
      )}

      <div className="flex-1 overflow-hidden neo-card p-0 bg-[#111] border border-[#333]">
        <div className="h-full overflow-y-auto p-2 font-mono text-xs text-gray-200">
          {logs.length === 0 ? (
            <div className="text-gray-500">No dev server logs yet.</div>
          ) : (
            <div className="space-y-0.5">
              {logs.map((l, idx) => (
                <div key={`${l.timestamp}-${idx}`} className="whitespace-pre-wrap break-all">
                  <span className="text-gray-600 select-none">
                    {new Date(l.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                  </span>
                  <span className="ml-2">{l.line}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

