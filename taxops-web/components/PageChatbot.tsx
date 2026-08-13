"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { X, Send, Loader2, Bot, Trash2 } from "lucide-react";
import { useApi } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string };

interface PageChatbotProps {
  /** Nombre del módulo que aparece en el botón y cabecera */
  moduleName: string;
  /** System prompt específico para este módulo */
  systemContext: string;
  /** Datos actuales del formulario/resultado para dar contexto al asistente */
  currentData?: Record<string, unknown> | null;
}

export function PageChatbot({ moduleName, systemContext, currentData }: PageChatbotProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const { post } = useApi();
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [messages, open]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((p) => [...p, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    const dataCtx = currentData
      ? `\n\nDatos actuales en pantalla:\n${JSON.stringify(currentData, null, 2)}`
      : "";

    try {
      const res = await post<{ content: string }>("/chatbot/contextual", {
        message: text,
        provider: "groq",
        model: "llama-3.3-70b-versatile",
        history: messages.map((m) => ({ role: m.role, content: m.content })),
        system_prompt: systemContext + dataCtx,
      });
      setMessages((p) => [...p, { role: "assistant", content: res.content }]);
    } catch {
      setMessages((p) => [
        ...p,
        { role: "assistant", content: "⚠️ Error al conectar con el asistente. Intenta de nuevo." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, currentData, systemContext, post]);

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        title={`Asistente ${moduleName}`}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-full shadow-2xl text-sm font-semibold transition-all duration-200 ${
          open
            ? "bg-slate-700 text-white hover:bg-slate-800"
            : "bg-brand-orange text-white hover:bg-orange-600 hover:scale-105"
        }`}
      >
        {open ? <X size={17} /> : <Bot size={17} />}
        {open ? "Cerrar chat" : `Asistente IA`}
        {!open && messages.length > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full text-[10px] flex items-center justify-center text-white">
            {messages.filter((m) => m.role === "assistant").length}
          </span>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="fixed bottom-20 right-6 z-50 flex flex-col bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-slate-700"
          style={{ width: 380, height: 500 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-brand-navy rounded-t-2xl flex-shrink-0">
            <div className="flex items-center gap-2">
              <Bot size={16} className="text-brand-orange" />
              <div>
                <p className="text-white text-sm font-semibold leading-tight">Asistente · {moduleName}</p>
                <p className="text-slate-400 text-[10px]">Llama 3.3 70B · Groq</p>
              </div>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                title="Limpiar conversación"
                className="text-slate-400 hover:text-white transition-colors"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-gray-400">
                <Bot size={36} className="opacity-20" />
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500">Asistente de {moduleName}</p>
                  <p className="text-xs">Pregúntame sobre cálculos, normativa CST,<br />o pídeme que te guíe paso a paso.</p>
                </div>
                <div className="flex flex-wrap gap-1 justify-center mt-2">
                  {[
                    "¿Qué es el IBC?",
                    "¿Cuándo aplica ARL clase III?",
                    "Explícame las cesantías",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => { setInput(q); inputRef.current?.focus(); }}
                      className="text-[11px] px-2 py-1 bg-gray-100 dark:bg-slate-700 rounded-full hover:bg-brand-orange hover:text-white transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[88%] rounded-2xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-brand-orange text-white rounded-br-sm"
                      : "bg-gray-100 dark:bg-slate-700 text-gray-800 dark:text-gray-100 rounded-bl-sm"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 dark:bg-slate-700 rounded-2xl rounded-bl-sm px-3 py-2 flex gap-1.5 items-center">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-100 dark:border-slate-700 flex gap-2 flex-shrink-0">
            <input
              ref={inputRef}
              className="flex-1 text-xs border border-gray-200 dark:border-slate-600 rounded-xl px-3 py-2 bg-white dark:bg-slate-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-orange placeholder:text-gray-400"
              placeholder="Escribe tu pregunta..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="p-2 bg-brand-orange text-white rounded-xl hover:bg-orange-600 disabled:opacity-40 transition-colors flex-shrink-0"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
