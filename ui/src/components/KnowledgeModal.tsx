/**
 * Knowledge Modal Component
 *
 * Manages per-project knowledge documents: markdown/text files (requirements
 * docs, research notes, ...) stored in .autoforge/knowledge/. Every agent
 * session is told to read them before planning or implementing features.
 */

import { useRef, useState } from 'react'
import { BookOpen, Eye, FileText, Loader2, Trash2, Upload, X } from 'lucide-react'
import {
  useDeleteKnowledgeFile,
  useKnowledgeFile,
  useKnowledgeFiles,
  useUploadKnowledgeFile,
} from '../hooks/useKnowledge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface KnowledgeModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

const MAX_FILE_SIZE = 1024 * 1024 // 1 MB, matches the server limit
const ALLOWED_EXTENSIONS = ['md', 'markdown', 'txt']

/**
 * Turn an arbitrary filename into one the server accepts:
 * letters, numbers, spaces, '.', '_' and '-', starting with a letter/number.
 */
function sanitizeFilename(name: string): string {
  const dot = name.lastIndexOf('.')
  const ext = name.slice(dot + 1).toLowerCase()
  const base = name
    .slice(0, dot)
    .replace(/[^A-Za-z0-9 _.-]/g, '_')
    .replace(/\.{2,}/g, '.')
    .replace(/^[^A-Za-z0-9]+/, '')
    .slice(0, 90)
    .replace(/[. ]+$/, '')
  return `${base || 'document'}.${ext}`
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

export function KnowledgeModal({ projectName, isOpen, onClose }: KnowledgeModalProps) {
  const { data, isLoading } = useKnowledgeFiles(isOpen ? projectName : null)
  const uploadFile = useUploadKnowledgeFile(projectName)
  const deleteFile = useDeleteKnowledgeFile(projectName)

  const [previewName, setPreviewName] = useState<string | null>(null)
  const { data: preview, isLoading: previewLoading } = useKnowledgeFile(
    isOpen ? projectName : null,
    previewName
  )

  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const files = data?.files ?? []

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    setError(null)

    const errors: string[] = []
    for (const file of Array.from(fileList)) {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
      if (!file.name.includes('.') || !ALLOWED_EXTENSIONS.includes(ext)) {
        errors.push(`${file.name}: only .md, .markdown and .txt files are supported`)
        continue
      }
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: exceeds the 1 MB limit`)
        continue
      }
      try {
        const content = await file.text()
        await uploadFile.mutateAsync({ filename: sanitizeFilename(file.name), content })
      } catch (err) {
        errors.push(`${file.name}: ${err instanceof Error ? err.message : 'upload failed'}`)
      }
    }

    if (errors.length > 0) setError(errors.join('\n'))
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDelete = async (filename: string) => {
    setError(null)
    try {
      await deleteFile.mutateAsync(filename)
      if (previewName === filename) setPreviewName(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete file')
    }
  }

  const handleClose = () => {
    setPreviewName(null)
    setError(null)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen size={18} className="text-primary" />
            Project Knowledge
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">
            Upload markdown documents such as requirements docs or research notes.
            Every agent session is told to read them before planning or implementing
            features. Files are stored in <code>.autoforge/knowledge/</code>; uploading
            a file with an existing name replaces it.
          </p>

          {/* Drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setIsDragging(false)
              handleFiles(e.dataTransfer.files)
            }}
            className={`flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-6 text-sm transition-colors ${
              isDragging ? 'border-primary bg-primary/10' : 'border-border'
            }`}
          >
            <Upload size={20} className="text-muted-foreground" />
            <span className="text-muted-foreground">Drag & drop .md / .txt files here, or</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadFile.isPending}
            >
              {uploadFile.isPending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              Choose files
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              multiple
              onChange={(e) => handleFiles(e.target.files)}
              className="hidden"
              aria-label="Upload knowledge files"
            />
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
            </Alert>
          )}

          {/* File list */}
          {isLoading ? (
            <div className="flex justify-center py-4">
              <Loader2 size={20} className="animate-spin text-muted-foreground" />
            </div>
          ) : files.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-2">
              No knowledge documents yet.
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {files.map((file) => (
                <li key={file.name} className="flex items-center gap-2 px-3 py-2">
                  <FileText size={16} className="shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate text-sm font-medium" title={file.name}>
                    {file.name}
                  </span>
                  <span className="text-xs text-muted-foreground">{formatSize(file.size)}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setPreviewName(previewName === file.name ? null : file.name)}
                    title={`Preview ${file.name}`}
                  >
                    <Eye size={16} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(file.name)}
                    disabled={deleteFile.isPending}
                    title={`Delete ${file.name}`}
                  >
                    <Trash2 size={16} className="text-destructive" />
                  </Button>
                </li>
              ))}
            </ul>
          )}

          {/* Preview */}
          {previewName && (
            <div className="rounded-md border border-border">
              <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
                <span className="truncate text-xs font-medium">{previewName}</span>
                <Button size="sm" variant="ghost" onClick={() => setPreviewName(null)} title="Close preview">
                  <X size={14} />
                </Button>
              </div>
              {previewLoading ? (
                <div className="flex justify-center py-4">
                  <Loader2 size={20} className="animate-spin text-muted-foreground" />
                </div>
              ) : (
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words p-3 text-xs">
                  {preview?.content}
                </pre>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
