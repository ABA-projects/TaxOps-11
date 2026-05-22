"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User } from "lucide-react";
import { useApi } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string };

const MODELS = [
  { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (recomendado)", provider: "groq" },
  { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B · Rápido", provider: "groq" },
  { value: "deepseek-r1-distill-llama-70b", label: "DeepSeek R1 70B · Razonamiento", provider: "groq" },
  { value: "gemma2-9b-it", label: "Gemma 2 9B · Google", provider: "groq" },
];

export default function ChatbotPage() {
  const { post } = useApi();
  const bottomRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hola, soy TaxOps Assistant — tu asistente contable colombiano. Puedo ayudarte con:\n\n• Normativa DIAN y facturación electrónica\n• Retención en la fuente y cálculos de IVA\n• Prorrateo Art. 490 ET\n• Exógenas y Formato 1003\n• Régimen simple, NIIF y más\n\n¿En qué puedo ayudarte hoy?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(MODELS[0].value);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    const modelConfig = MODELS.find((m) => m.value === selectedModel) ?? MODELS[0];

    try {
      const res = await post<{ content: string }>("/chatbot/ask", {
        message: text,
        provider: modelConfig.provider,
        model: selectedModel,
        history: messages.slice(-10), // últimos 10 mensajes de contexto
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.content }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Lo siento, ocurrió un error. Intenta de nuevo.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-3xl">
      {/* Model selector */}
      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm text-gray-500">Modelo:</label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-brand-orange"
        >
          {MODELS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
        <span className="text-xs text-emerald-600 font-medium bg-emerald-50 px-2 py-1 rounded-full">
          Gratis · Groq
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto card p-4 space-y-4 mb-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                msg.role === "assistant"
                  ? "bg-brand-navy text-white"
                  : "bg-brand-orange text-white"
              }`}
            >
              {msg.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
            </div>
            <div
              className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                msg.role === "assistant"
                  ? "bg-gray-100 text-gray-800"
                  : "bg-brand-orange text-white"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-brand-navy flex items-center justify-center">
              <Bot size={16} className="text-white" />
            </div>
            <div className="bg-gray-100 rounded-2xl px-4 py-3 flex items-center gap-1.5">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Pregunta sobre normativa DIAN, retención, IVA..."
          className="input flex-1"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="btn-primary px-4 flex items-center gap-2"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
