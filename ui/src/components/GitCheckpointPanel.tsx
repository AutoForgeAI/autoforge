/**
 * Git Checkpoint Panel
 *
 * Panel for git repository management including:
 * - Initialize git repository
 * - Manage remotes (add/edit/remove)
 * - Create checkpoint commits with detailed messages
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GitBranch,
  FileEdit,
  FilePlus,
  Check,
  Loader2,
  AlertCircle,
  Save,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Link,
  Plus,
  Trash2,
  ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import * as api from '@/lib/api'

interface GitCheckpointPanelProps {
  projectName: string | null
  className?: string
  onSuccess?: () => void
}

export function GitCheckpointPanel({
  projectName,
  className = '',
  onSuccess,
}: GitCheckpointPanelProps) {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState('')
  const [description, setDescription] = useState('')
  const [showDiff, setShowDiff] = useState(false)
  const [showRemoteForm, setShowRemoteForm] = useState(false)
  const [remoteUrl, setRemoteUrl] = useState('')
  const [remoteName, setRemoteName] = useState('origin')

  // Fetch git status
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = useQuery({
    queryKey: ['git-status', projectName],
    queryFn: () => api.getGitStatus(projectName!),
    enabled: !!projectName,
    refetchInterval: 10000,
  })

  // Fetch git remotes
  const { data: remotesData, refetch: refetchRemotes } = useQuery({
    queryKey: ['git-remotes', projectName],
    queryFn: () => api.getGitRemotes(projectName!),
    enabled: !!projectName && status?.isRepo,
  })

  // Fetch git diff
  const { data: diff, isLoading: diffLoading } = useQuery({
    queryKey: ['git-diff', projectName],
    queryFn: () => api.getGitDiff(projectName!),
    enabled: !!projectName && showDiff && status?.isRepo,
  })

  // Initialize git mutation
  const initGit = useMutation({
    mutationFn: () => api.initGitRepo(projectName!, { initialBranch: 'main' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['git-status', projectName] })
      queryClient.invalidateQueries({ queryKey: ['git-remotes', projectName] })
    },
  })

  // Set remote mutation
  const setRemote = useMutation({
    mutationFn: () =>
      api.setGitRemote(projectName!, { name: remoteName, url: remoteUrl }),
    onSuccess: () => {
      setRemoteUrl('')
      setRemoteName('origin')
      setShowRemoteForm(false)
      refetchRemotes()
    },
  })

  // Remove remote mutation
  const removeRemote = useMutation({
    mutationFn: (name: string) => api.removeGitRemote(projectName!, name),
    onSuccess: () => {
      refetchRemotes()
    },
  })

  // Create checkpoint mutation
  const createCheckpoint = useMutation({
    mutationFn: () =>
      api.createCheckpoint(projectName!, {
        message: message.trim(),
        description: description.trim() || undefined,
      }),
    onSuccess: (result) => {
      if (result.success) {
        setMessage('')
        setDescription('')
        queryClient.invalidateQueries({ queryKey: ['git-status', projectName] })
        queryClient.invalidateQueries({ queryKey: ['git-diff', projectName] })
        onSuccess?.()
      }
    },
  })

  if (!projectName) {
    return (
      <div className={`p-4 text-muted-foreground ${className}`}>
        Select a project to manage git
      </div>
    )
  }

  if (statusLoading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <Loader2 className="animate-spin" size={24} />
        <span className="ml-2">Loading git status...</span>
      </div>
    )
  }

  if (statusError) {
    return (
      <Alert variant="destructive" className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>Failed to load git status</AlertDescription>
      </Alert>
    )
  }

  // Not a git repo - show init option
  if (!status?.isRepo) {
    return (
      <div className={`space-y-4 ${className}`}>
        <Alert>
          <GitBranch className="h-4 w-4" />
          <AlertDescription>
            This project is not a git repository.
          </AlertDescription>
        </Alert>

        <Button
          onClick={() => initGit.mutate()}
          disabled={initGit.isPending}
          className="w-full gap-2"
        >
          {initGit.isPending ? (
            <>
              <Loader2 className="animate-spin" size={16} />
              Initializing...
            </>
          ) : (
            <>
              <GitBranch size={16} />
              Initialize Git Repository
            </>
          )}
        </Button>

        {initGit.isSuccess && initGit.data?.success && (
          <Alert>
            <Check className="h-4 w-4 text-green-500" />
            <AlertDescription>{initGit.data.message}</AlertDescription>
          </Alert>
        )}

        {initGit.isSuccess && !initGit.data?.success && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{initGit.data?.message}</AlertDescription>
          </Alert>
        )}
      </div>
    )
  }

  const hasChanges = (status.modified ?? 0) + (status.staged ?? 0) + (status.untracked ?? 0) > 0
  const totalChanges = (status.modified ?? 0) + (status.staged ?? 0) + (status.untracked ?? 0)
  const isValid = message.trim().length > 0
  const remotes = remotesData?.remotes ?? []
  const hasRemote = remotes.length > 0

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Repository Status */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <GitBranch size={16} className="text-primary" />
              <span className="font-medium">{status.branch || 'HEAD'}</span>
            </div>

            {hasChanges ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                {(status.staged ?? 0) > 0 && (
                  <span className="flex items-center gap-0.5 text-green-500">
                    <Check size={12} />
                    {status.staged}
                  </span>
                )}
                {(status.modified ?? 0) > 0 && (
                  <span className="flex items-center gap-0.5 text-yellow-500">
                    <FileEdit size={12} />
                    {status.modified}
                  </span>
                )}
                {(status.untracked ?? 0) > 0 && (
                  <span className="flex items-center gap-0.5 text-blue-500">
                    <FilePlus size={12} />
                    {status.untracked}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <Check size={12} className="text-green-500" />
                Clean
              </span>
            )}
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchStatus()}
            className="h-8 w-8 p-0"
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {/* Remote Management */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium flex items-center gap-2">
            <Link size={14} />
            Remote Repositories
          </Label>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowRemoteForm(!showRemoteForm)}
            className="h-7 gap-1 text-xs"
          >
            <Plus size={12} />
            {showRemoteForm ? 'Cancel' : 'Add Remote'}
          </Button>
        </div>

        {/* Existing Remotes */}
        {remotes.length > 0 ? (
          <div className="space-y-2">
            {remotes.map((remote) => (
              <div
                key={remote.name}
                className="flex items-center justify-between gap-2 p-2 bg-muted/50 rounded-md"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-sm font-medium">{remote.name}</span>
                  <span className="text-xs text-muted-foreground truncate">
                    {remote.url}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    onClick={() => window.open(remote.url.replace(/\.git$/, ''), '_blank')}
                    title="Open in browser"
                  >
                    <ExternalLink size={12} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                    onClick={() => removeRemote.mutate(remote.name)}
                    disabled={removeRemote.isPending}
                    title="Remove remote"
                  >
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No remotes configured. Add a remote to push your code.
          </p>
        )}

        {/* Add Remote Form */}
        {showRemoteForm && (
          <div className="space-y-2 p-3 border rounded-md bg-muted/30">
            <div className="grid grid-cols-4 gap-2">
              <div>
                <Label htmlFor="remote-name" className="text-xs">
                  Name
                </Label>
                <Input
                  id="remote-name"
                  placeholder="origin"
                  value={remoteName}
                  onChange={(e) => setRemoteName(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div className="col-span-3">
                <Label htmlFor="remote-url" className="text-xs">
                  URL
                </Label>
                <Input
                  id="remote-url"
                  placeholder="https://github.com/user/repo.git"
                  value={remoteUrl}
                  onChange={(e) => setRemoteUrl(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <Button
              size="sm"
              onClick={() => setRemote.mutate()}
              disabled={!remoteUrl.trim() || !remoteName.trim() || setRemote.isPending}
              className="w-full gap-2"
            >
              {setRemote.isPending ? (
                <Loader2 className="animate-spin" size={14} />
              ) : (
                <Link size={14} />
              )}
              {hasRemote ? 'Update Remote' : 'Add Remote'}
            </Button>
          </div>
        )}

        {setRemote.isSuccess && setRemote.data && (
          <Alert className={setRemote.data.success ? '' : 'border-destructive'}>
            {setRemote.data.success ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            <AlertDescription>{setRemote.data.message}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Checkpoint Commit */}
      <div className="space-y-3">
        <Label className="text-sm font-medium flex items-center gap-2">
          <Save size={14} />
          Create Checkpoint
        </Label>

        {/* Diff Preview */}
        {hasChanges && (
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDiff(!showDiff)}
              className="gap-2 text-muted-foreground h-7 text-xs"
            >
              {showDiff ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {totalChanges} file{totalChanges !== 1 ? 's' : ''} to commit
            </Button>
            {showDiff && (
              <div className="mt-2 bg-muted/50 rounded-lg p-3 text-xs font-mono max-h-32 overflow-y-auto">
                {diffLoading ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="animate-spin" size={12} />
                    Loading diff...
                  </div>
                ) : diff ? (
                  <div className="space-y-2">
                    {diff.stagedDiff && (
                      <div>
                        <div className="text-green-500 mb-1">Staged:</div>
                        <pre className="whitespace-pre-wrap text-muted-foreground">
                          {diff.stagedDiff}
                        </pre>
                      </div>
                    )}
                    {diff.unstagedDiff && (
                      <div>
                        <div className="text-yellow-500 mb-1">Modified:</div>
                        <pre className="whitespace-pre-wrap text-muted-foreground">
                          {diff.unstagedDiff}
                        </pre>
                      </div>
                    )}
                    {diff.untrackedFiles.length > 0 && (
                      <div>
                        <div className="text-blue-500 mb-1">Untracked:</div>
                        {diff.untrackedFiles.slice(0, 10).map((file) => (
                          <div key={file} className="text-muted-foreground">
                            {file}
                          </div>
                        ))}
                        {diff.untrackedFiles.length > 10 && (
                          <div className="text-muted-foreground">
                            ...and {diff.untrackedFiles.length - 10} more
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="text-muted-foreground">No changes to show</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Commit Form */}
        <div>
          <Input
            placeholder="feat: add new feature"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={72}
            className="text-sm"
          />
          <p className="text-xs text-muted-foreground mt-1">
            {message.length}/72 characters
          </p>
        </div>

        <Textarea
          placeholder="Detailed description (optional)..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="min-h-[60px] resize-y text-sm"
        />

        {/* Result Message */}
        {createCheckpoint.isSuccess && createCheckpoint.data && (
          <Alert className={createCheckpoint.data.success ? '' : 'border-destructive'}>
            {createCheckpoint.data.success ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            <AlertDescription>
              {createCheckpoint.data.message}
              {createCheckpoint.data.success && createCheckpoint.data.commitHash && (
                <span className="ml-2 font-mono text-xs bg-muted px-1 py-0.5 rounded">
                  {createCheckpoint.data.commitHash}
                </span>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Create Button */}
        <Button
          onClick={() => createCheckpoint.mutate()}
          disabled={!isValid || !hasChanges || createCheckpoint.isPending}
          className="w-full gap-2"
        >
          {createCheckpoint.isPending ? (
            <>
              <Loader2 className="animate-spin" size={16} />
              Creating checkpoint...
            </>
          ) : (
            <>
              <Save size={16} />
              Create Checkpoint
              {hasChanges && (
                <span className="ml-1 text-xs opacity-70">
                  ({totalChanges} file{totalChanges !== 1 ? 's' : ''})
                </span>
              )}
            </>
          )}
        </Button>

        {!hasChanges && (
          <p className="text-sm text-muted-foreground text-center">
            No changes to commit
          </p>
        )}
      </div>
    </div>
  )
}

export default GitCheckpointPanel
