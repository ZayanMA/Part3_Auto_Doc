'use client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="prose prose-base max-w-none prose-headings:text-gray-900 prose-code:text-blue-700 prose-pre:bg-gray-900 prose-pre:rounded-lg prose-pre:p-0">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
