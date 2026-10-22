import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, ExternalLink, Github, Loader2, Search } from 'lucide-react'
import { getGitHubRepo, importGitHubIssues, listGitHubIssues } from '../lib/api'
import type { GitHubIssue } from '../lib/types'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface GitHubImportModalProps {
  projectName: string
  onClose: () => void
}

type IssueState = 'open' | 'closed' | 'all'

/**
 * Import issues from a GitHub repository as pending features.
 *
 * The repository is detected from the project's git remote when possible.
 * Each selected issue becomes one feature (task-list items become its steps).
 */
export function GitHubImportModal({ projectName, onClose }: GitHubImportModalProps) {
  const queryClient = useQueryClient()
  const [repo, setRepo] = useState('')
  const [issueState, setIssueState] = useState<IssueState>('open')
  const [loadedRepo, setLoadedRepo] = useState<string | null>(null)
  const [issues, setIssues] = useState<GitHubIssue[]>([])
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState('')
  const [includeComments, setIncludeComments] = useState(true)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const loadIssues = async (repoName: string, state: IssueState = issueState) => {
    if (!repoName.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await listGitHubIssues(projectName, repoName.trim(), state)
      setLoadedRepo(data.repo)
      setRepo(data.repo)
      setIssues(data.issues)
      setAuthenticated(data.authenticated)
      setSelected(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load issues')
      setIssues([])
      setLoadedRepo(null)
    } finally {
      setLoading(false)
    }
  }

  // Detect the repository from the project's git remote on open
  useEffect(() => {
    let cancelled = false
    getGitHubRepo(projectName)
      .then((info) => {
        if (cancelled) return
        setAuthenticated(info.authenticated)
        if (info.repo) {
          setRepo(info.repo)
          loadIssues(info.repo)
        }
      })
      .catch(() => { /* user can still type the repo */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectName])

  const visibleIssues = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return issues
    return issues.filter(i =>
      i.title.toLowerCase().includes(q) ||
      String(i.number) === q.replace('#', '') ||
      i.labels.some(l => l.toLowerCase().includes(q))
    )
  }, [issues, filter])

  const selectable = visibleIssues.filter(i => i.imported_feature_id === null)
  const allSelected = selectable.length > 0 && selectable.every(i => selected.has(i.number))

  const toggle = (num: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(num)) next.delete(num)
      else next.add(num)
      return next
    })
  }

  const toggleAll = () => {
    setSelected(prev => {
      const next = new Set(prev)
      if (allSelected) selectable.forEach(i => next.delete(i.number))
      else selectable.slice(0, 50).forEach(i => next.add(i.number))
      return next
    })
  }

  const handleImport = async () => {
    if (!loadedRepo || selected.size === 0) return
    setImporting(true)
    setError(null)
    setResult(null)
    try {
      const numbers = [...selected].slice(0, 50)
      const res = await importGitHubIssues(projectName, loadedRepo, numbers, includeComments)
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
      const imported = new Map(res.features.map(f => [Number(f.name.match(/^#(\d+)/)?.[1]), f.id]))
      setIssues(prev => prev.map(i => imported.has(i.number) ? { ...i, imported_feature_id: imported.get(i.number)! } : i))
      setSelected(new Set())
      setResult(
        `Imported ${res.created} issue${res.created === 1 ? '' : 's'} as pending features` +
        (res.skipped.length ? ` (${res.skipped.length} already imported)` : '') + '.'
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import issues')
    } finally {
      setImporting(false)
    }
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Github size={20} />
            Import GitHub Issues
          </DialogTitle>
          <DialogDescription>
            Turn issues from your repository into pending features for the coding agent.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col sm:flex-row gap-2 sm:items-end"
          onSubmit={(e) => { e.preventDefault(); loadIssues(repo) }}
        >
          <div className="flex-1 space-y-2">
            <Label htmlFor="github-repo">Repository</Label>
            <Input
              id="github-repo"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              placeholder="owner/name"
              autoComplete="off"
            />
          </div>
          <select
            aria-label="Issue state"
            className="h-9 rounded-md border bg-background px-3 text-sm"
            value={issueState}
            onChange={(e) => {
              const s = e.target.value as IssueState
              setIssueState(s)
              if (loadedRepo) loadIssues(loadedRepo, s)
            }}
          >
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="all">All</option>
          </select>
          <Button type="submit" disabled={loading || !repo.trim()}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Load issues
          </Button>
        </form>

        {authenticated === false && (
          <p className="text-xs text-muted-foreground">
            Not authenticated with GitHub: only public repositories work, with a low rate limit.
            Set <code>GITHUB_TOKEN</code> in your environment or run <code>gh auth login</code>.
          </p>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {result && (
          <Alert>
            <CheckCircle2 className="h-4 w-4" />
            <AlertDescription>{result}</AlertDescription>
          </Alert>
        )}

        {loadedRepo && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter by title, #number or label"
                className="flex-1"
                aria-label="Filter issues"
              />
              <Button type="button" variant="outline" size="sm" onClick={toggleAll} disabled={selectable.length === 0}>
                {allSelected ? 'Clear' : 'Select all'}
              </Button>
            </div>

            <div className="max-h-[40vh] overflow-y-auto border rounded-md divide-y">
              {visibleIssues.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground text-sm">
                  {loading ? 'Loading…' : 'No issues found'}
                </div>
              ) : (
                visibleIssues.map(issue => {
                  const imported = issue.imported_feature_id !== null
                  const checkboxId = `gh-issue-${issue.number}`
                  return (
                    <div key={issue.number} className={`flex items-start gap-3 p-3 ${imported ? 'opacity-60' : ''}`}>
                      <Checkbox
                        id={checkboxId}
                        checked={selected.has(issue.number)}
                        disabled={imported}
                        onCheckedChange={() => toggle(issue.number)}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <label htmlFor={checkboxId} className="font-medium cursor-pointer break-words">
                          <span className="text-muted-foreground font-mono mr-1">#{issue.number}</span>
                          {issue.title}
                        </label>
                        <div className="flex flex-wrap items-center gap-1 mt-1">
                          {issue.state === 'closed' && <Badge variant="outline">closed</Badge>}
                          {imported && <Badge variant="secondary">already imported</Badge>}
                          {issue.labels.map(l => <Badge key={l} variant="outline">{l}</Badge>)}
                        </div>
                      </div>
                      <a
                        href={issue.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-muted-foreground hover:text-foreground"
                        title="Open on GitHub"
                      >
                        <ExternalLink size={16} />
                      </a>
                    </div>
                  )
                })
              )}
            </div>

            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={includeComments}
                onCheckedChange={(v) => setIncludeComments(v === true)}
              />
              Include issue comments in the feature description
            </label>
          </div>
        )}

        <DialogFooter className="pt-4 border-t">
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button type="button" onClick={handleImport} disabled={!loadedRepo || selected.size === 0 || importing}>
            {importing && <Loader2 size={16} className="animate-spin" />}
            Import {selected.size > 0 ? selected.size : ''} as features
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
