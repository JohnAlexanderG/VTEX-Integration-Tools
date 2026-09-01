import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Props {
  source: string
}

/**
 * Render de markdown para la documentación de las herramientas.
 *
 * react-markdown construye un árbol de elementos React y nunca usa
 * dangerouslySetInnerHTML sobre el fuente, así que los placeholders con
 * ángulos que abundan en los README (`<archivo>`, `<sku>`) se muestran como
 * texto y no hay superficie de XSS. El HTML crudo se descarta (no cargamos
 * rehype-raw a propósito).
 */
export default function Markdown({ source }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h2 className="mt-5 mb-2 text-sm font-bold text-ink-1 first:mt-0">{children}</h2>
        ),
        h2: ({ children }) => (
          <h3 className="mt-5 mb-2 text-sm font-semibold text-ink-1 first:mt-0">{children}</h3>
        ),
        h3: ({ children }) => (
          <h4 className="mt-4 mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">
            {children}
          </h4>
        ),
        h4: ({ children }) => (
          <h5 className="mt-3 mb-1 text-xs font-semibold text-ink-2">{children}</h5>
        ),
        p: ({ children }) => <p className="mb-3 leading-relaxed text-ink-3">{children}</p>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            {children}
          </a>
        ),
        ul: ({ children }) => (
          <ul className="mb-3 ml-5 list-disc space-y-1 text-ink-3">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 ml-5 list-decimal space-y-1 text-ink-3">{children}</ol>
        ),
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-ink-1">{children}</strong>,
        code: ({ className, children }) => {
          // Sin className = code span inline; con className = bloque con lenguaje.
          const isBlock = Boolean(className)
          if (isBlock) return <code className="block">{children}</code>
          return (
            <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[11px] text-ink-2">
              {children}
            </code>
          )
        },
        pre: ({ children }) => (
          <pre className="scrollbar-thin mb-3 overflow-x-auto rounded-control border border-line-1 bg-surface-0 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-green-300">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="mb-3 border-l-2 border-line-2 pl-3 text-ink-4">{children}</blockquote>
        ),
        hr: () => <hr className="my-4 border-line-1" />,
        table: ({ children }) => (
          <div className="scrollbar-thin mb-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-[11px]">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-b border-line-2 px-2 py-1.5 font-semibold text-ink-2">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border-b border-line-1 px-2 py-1.5 align-top text-ink-3">{children}</td>
        ),
        img: ({ src, alt }) => (
          <img src={src} alt={alt} className="mb-3 max-w-full rounded-control border border-line-1" />
        ),
      }}
    >
      {source}
    </ReactMarkdown>
  )
}
