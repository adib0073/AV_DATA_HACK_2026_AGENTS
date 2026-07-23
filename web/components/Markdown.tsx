"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Compact, theme-matched markdown renderer for chat responses and tiles.
 * The agents return markdown (headings, bold, bullet lists); this turns it into
 * proper HTML instead of showing raw `###`/`**` tokens.
 */
export default function Markdown({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={`space-y-2 text-sm leading-relaxed text-slate-700 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="mt-1 text-[15px] font-bold text-slate-900">{children}</h3>
          ),
          h2: ({ children }) => (
            <h4 className="mt-1 text-sm font-bold text-slate-900">{children}</h4>
          ),
          h3: ({ children }) => (
            <h4 className="mt-1 text-[13px] font-bold text-slate-900">{children}</h4>
          ),
          h4: ({ children }) => (
            <h5 className="mt-1 text-[13px] font-semibold text-slate-800">{children}</h5>
          ),
          p: ({ children }) => <p className="text-slate-700">{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5 marker:text-slate-400">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5 marker:text-slate-400">{children}</ol>
          ),
          li: ({ children }) => <li className="text-slate-700">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-2 hover:text-brand-700"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[12px] text-slate-800">
              {children}
            </code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-brand-200 pl-3 text-slate-600">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="border-slate-200" />,
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-slate-200 px-2 py-1 font-semibold text-slate-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-slate-100 px-2 py-1 text-slate-600">{children}</td>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
