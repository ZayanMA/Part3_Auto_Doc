'use client'
import type { Components } from 'react-markdown'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

export default function MarkdownRenderer({ content }: { content: string }) {
  const components: Components = {
    h1: ({ children }) => <h1 className="doc-h1">{children}</h1>,
    h2: ({ children }) => <h2 className="doc-h2">{children}</h2>,
    h3: ({ children }) => <h3 className="doc-h3">{children}</h3>,
    p: ({ children }) => <p className="doc-p">{children}</p>,
    ul: ({ children }) => <ul className="doc-ul">{children}</ul>,
    ol: ({ children }) => <ol className="doc-ol">{children}</ol>,
    li: ({ children }) => <li className="doc-li">{children}</li>,
    a: ({ children, href }) => (
      <a href={href} className="doc-link" target="_blank" rel="noreferrer">
        {children}
      </a>
    ),
    blockquote: ({ children }) => <blockquote className="doc-blockquote">{children}</blockquote>,
    hr: () => <hr className="doc-hr" />,
    table: ({ children }) => (
      <div className="doc-table-wrap">
        <table className="doc-table">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="doc-thead">{children}</thead>,
    th: ({ children }) => <th className="doc-th">{children}</th>,
    td: ({ children }) => <td className="doc-td">{children}</td>,
    code: ({ children, className, ...props }) => {
      const isBlock = Boolean(className)
      if (isBlock) {
        return (
          <code className={className} {...props}>
            {children}
          </code>
        )
      }
      return (
        <code className="doc-inline-code" {...props}>
          {children}
        </code>
      )
    },
    pre: ({ children }) => <pre className="doc-pre">{children}</pre>,
  }

  return (
    <div className="doc-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
