"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renderiza la respuesta del asistente como markdown.
 *
 * El LLM responde en markdown (encabezados, negritas, tablas, listas) y hasta ahora el chat lo
 * mostraba como texto plano: se veían los asteriscos crudos, las tablas como pipes sueltos y
 * algún <br> literal. remark-gfm es lo que habilita tablas, que el asistente usa bastante para
 * comparar vencimientos y conceptos.
 *
 * Los mensajes del usuario NO pasan por acá: son texto que él escribió, no markdown.
 */
export default function ChatMarkdown({ content, compact = false }: { content: string; compact?: boolean }) {
  const t = compact ? "text-xs" : "text-sm";
  return (
    <div className={`${t} leading-relaxed space-y-2`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="text-base font-semibold mt-1 mb-1" {...p} />,
          h2: (p) => <h2 className="text-sm font-semibold mt-2 mb-1" {...p} />,
          h3: (p) => <h3 className="text-sm font-semibold mt-2 mb-0.5" {...p} />,
          h4: (p) => <h4 className="font-semibold mt-2 mb-0.5" {...p} />,
          p: (p) => <p className="mb-2 last:mb-0" {...p} />,
          ul: (p) => <ul className="list-disc pl-4 space-y-0.5 mb-2" {...p} />,
          ol: (p) => <ol className="list-decimal pl-4 space-y-0.5 mb-2" {...p} />,
          strong: (p) => <strong className="font-semibold" {...p} />,
          a: (p) => (
            <a className="text-brand-orange underline underline-offset-2" target="_blank" rel="noreferrer" {...p} />
          ),
          code: (p) => <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-[0.9em]" {...p} />,
          // Las tablas del asistente suelen ser anchas: scrollean solas en vez de romper la burbuja.
          table: (p) => (
            <div className="overflow-x-auto my-2">
              <table className="w-full border-collapse text-[0.95em]" {...p} />
            </div>
          ),
          th: (p) => <th className="border border-black/10 dark:border-white/15 px-2 py-1 text-left font-semibold" {...p} />,
          td: (p) => <td className="border border-black/10 dark:border-white/15 px-2 py-1 align-top" {...p} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
