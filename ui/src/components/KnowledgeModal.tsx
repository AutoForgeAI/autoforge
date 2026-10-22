/**
 * Knowledge Modal Component
 *
 * Lets the user upload markdown/text reference documents (requirements,
 * research notes, ...) to the project's .autoforge/knowledge/ folder.
 * Agents are pointed at these files at the start of every session.
 */

import { useRef, useState } from 'react'
import { BookOpen, ChevronDown, ChevronRight, FileText, Loader2, Trash2, Upload } from 'lucide-react'
import {
  useKnowledgeFiles,
  useKnowledgeFile,
  useUploadKnowledgeFile,
  useDeleteKnowledgeFile,
} from '../hooks/useKnowledge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'

// Keep in sync with server/routers/knowledge.py
const MAX_FILE_SIZE = 1024 * 1024
const ACCEPTED_EXTENSIONS = ['.md', '.markdown', '.txt']

/** Turn an arbitrary filename into one the server accepts. */
function sanitizeFilename(name: string): string {
  const dot = name.lastIndexOf('.')
  const ext = dot >= 0 ? name.slice(dot).toLowerCase() : ''
  let base = (dot >= 0 ? name.slice(0, dot) : name).replace(/[^A-Za-z0-9 ._()-]/g, '_')
  base = base.replace(/\.{2,}/g, '.').replace(/^[^A-Za-z0-9]+/, '').slice(0, 90)
  return `${base || 'document'}${ext}`
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`
}

interface KnowledgeModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

export function KnowledgeModal({ projectName, isOpen, onClose }: KnowledgeModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { data: files, isLoading } = useKnowledgeFiles(projectName, isOpen)
  const uploadFile = useUploadKnowledgeFile(projectName)
  const deleteFile = useDeleteKnowledgeFile(projectName)

  const [expanded, setExpanded] = useState<string | null>(null)
  const { data: preview, isLoading: previewLoading } = useKnowledgeFile(projectName, expanded)

  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    setError(null)
    const errors: string[] = []

    for (const file of Array.from(fileList)) {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        errors.push(`${file.name}: only .md, .markdown and .txt files are supported`)
        continue
      }
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: file is larger than 1 MB`)
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
      if (expanded === filename) setExpanded(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete file')
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[650px] max-h-[80vh] flex flex-col p-0">
        <DialogHeader className="p-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <BookOpen size={24} className="text-primary" />
            Project Knowledge
          </DialogTitle>
          <DialogDescription>
            Upload markdown or text documents (requirements, research, design notes) with extra
            context for this project. Agents are told to read them at the start of every session.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-6">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
            </Alert>
          )}

          {/* Upload drop zone */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                fileInputRef.current?.click()
              }
            }}
            onDragOver={(e) => {
              e.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setIsDragging(false)
              void handleFiles(e.dataTransfer.files)
            }}
            className={`mb-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              isDragging ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/60'
            }`}
            data-testid="knowledge-dropzone"
          >
            {uploadFile.isPending ? (
              <Loader2 size={28} className="animate-spin text-primary" />
            ) : (
              <Upload size={28} className="text-muted-foreground" />
            )}
            <span className="text-sm font-medium">Drop .md files here or click to upload</span>
            <span className="text-xs text-muted-foreground">
              .md, .markdown or .txt, up to 1 MB each. Uploading a file with the same name replaces it.
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS.join(',')}
              multiple
              className="hidden"
              onChange={(e) => void handleFiles(e.target.files)}
              data-testid="knowledge-file-input"
            />
          </div>

          {/* File list */}
          {isLoading ? (
            <div className="text-center py-6 text-muted-foreground">Loading files...</div>
          ) : files && files.length > 0 ? (
            <div className="space-y-2">
              {files.map((file) => {
                const isExpanded = expanded === file.filename
                return (
                  <Card key={file.filename} className="py-0 gap-0">
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => setExpanded(isExpanded ? null : file.filename)}
                          className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          title={isExpanded ? 'Hide preview' : 'Show preview'}
                        >
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          <FileText size={16} className="shrink-0 text-primary" />
                          <span className="truncate font-medium">{file.filename}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {formatSize(file.size)}
                          </span>
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleDelete(file.filename)}
                          disabled={deleteFile.isPending}
                          className="text-destructive hover:text-destructive"
                          title={`Delete ${file.filename}`}
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                      {isExpanded && (
                        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded border border-border bg-muted p-3 text-xs">
                          {previewLoading ? 'Loading...' : preview?.content}
                        </pre>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <BookOpen size={40} className="mx-auto mb-2 opacity-50" />
              <p>No knowledge files yet</p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
