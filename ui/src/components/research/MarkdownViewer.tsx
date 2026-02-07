/**
 * MarkdownViewer Component
 *
 * Renders markdown content with syntax highlighting for code blocks
 * and copy-to-clipboard functionality.
 */

import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface MarkdownViewerProps {
  content: string
  className?: string
}

interface CodeBlockProps {
  inline?: boolean
  className?: string
  children?: React.ReactNode
  node?: unknown
}

/**
 * CodeBlock component with syntax highlighting and copy functionality
 */
function CodeBlock({ inline, className, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  // Extract language from className (format: "language-xxx")
  const match = /language-(\w+)/.exec(className || '')
  const language = match ? match[1] : ''
  const codeString = String(children).replace(/\n$/, '')

  // Detect dark mode by checking document class
  const isDarkMode = typeof document !== 'undefined'
    ? document.documentElement.classList.contains('dark')
    : false

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(codeString)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy code:', err)
    }
  }, [codeString])

  // Determine if this is inline code:
  // - explicitly marked as inline by react-markdown
  // - OR no language class AND no newlines in content (single backtick code)
  const isInlineCode = inline || (!className && !codeString.includes('\n'))

  // Inline code styling - render as simple styled <code> element
  if (isInlineCode) {
    return (
      <code className="bg-muted/70 px-1.5 py-0.5 rounded text-[0.9em] font-mono text-foreground">
        {children}
      </code>
    )
  }

  // Block code with syntax highlighting - subtle, not card-like
  return (
    <div className="relative group my-4 rounded-md overflow-hidden border border-border/50">
      {/* Language label and copy button - positioned inside */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/40 border-b border-border/30">
        <span className="text-xs text-muted-foreground font-medium">
          {language || 'text'}
        </span>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={handleCopy}
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6"
          title={copied ? 'Copied!' : 'Copy code'}
        >
          {copied ? (
            <Check size={12} className="text-primary" />
          ) : (
            <Copy size={12} />
          )}
        </Button>
      </div>

      <SyntaxHighlighter
        style={isDarkMode ? oneDark : oneLight}
        language={language || 'text'}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: '0.8125rem',
          padding: '0.875rem 1rem',
          background: 'var(--muted)',
          opacity: 0.6,
        }}
        codeTagProps={{
          style: {
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.6,
          },
        }}
      >
        {codeString}
      </SyntaxHighlighter>
    </div>
  )
}

/**
 * MarkdownViewer renders markdown content with GFM support
 * and syntax-highlighted code blocks.
 */
export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
  return (
    <div
      className={cn(
        // Base prose styling - simplified for cleaner rendering
        'prose prose-sm dark:prose-invert max-w-none',
        // Headings - clear visual hierarchy
        'prose-headings:font-semibold prose-headings:text-foreground prose-headings:leading-tight',
        'prose-h1:text-2xl prose-h1:border-b prose-h1:border-border/50 prose-h1:pb-3 prose-h1:mb-6 prose-h1:mt-0',
        'prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4',
        'prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3',
        'prose-h4:text-base prose-h4:mt-4 prose-h4:mb-2',
        // Paragraphs and text - good readability
        'prose-p:text-foreground prose-p:leading-7 prose-p:my-4',
        'prose-strong:text-foreground prose-strong:font-semibold',
        // Lists - proper indentation and spacing
        'prose-ul:my-4 prose-ul:pl-6 prose-ol:my-4 prose-ol:pl-6',
        'prose-li:text-foreground prose-li:my-1 prose-li:leading-7',
        'prose-ul:list-disc prose-ol:list-decimal',
        // Nested lists
        '[&_ul_ul]:my-1 [&_ol_ol]:my-1 [&_ul_ol]:my-1 [&_ol_ul]:my-1',
        // Links
        'prose-a:text-primary prose-a:underline prose-a:underline-offset-2 hover:prose-a:text-primary/80',
        // Inline code - subtle styling
        'prose-code:text-sm prose-code:text-foreground prose-code:bg-muted/60 prose-code:rounded prose-code:px-1.5 prose-code:py-0.5 prose-code:font-normal',
        'prose-code:before:content-none prose-code:after:content-none',
        // Code blocks - transparent wrapper so our custom CodeBlock handles it
        'prose-pre:bg-transparent prose-pre:p-0 prose-pre:my-4',
        // Tables - clean borders
        'prose-table:border prose-table:border-border prose-table:my-6',
        'prose-th:border prose-th:border-border prose-th:bg-muted/50 prose-th:px-4 prose-th:py-2 prose-th:text-left prose-th:font-semibold',
        'prose-td:border prose-td:border-border prose-td:px-4 prose-td:py-2',
        // Blockquotes - subtle left border
        'prose-blockquote:border-l-4 prose-blockquote:border-primary/30 prose-blockquote:bg-muted/30 prose-blockquote:py-2 prose-blockquote:px-4 prose-blockquote:my-4 prose-blockquote:not-italic',
        // Horizontal rules
        'prose-hr:border-border prose-hr:my-8',
        // Images
        'prose-img:rounded-lg prose-img:my-4',
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: CodeBlock as React.ComponentType<React.HTMLAttributes<HTMLElement>>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
