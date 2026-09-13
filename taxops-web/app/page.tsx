"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Bell, Bot, Calculator, Calendar, Check, ClipboardList, Download, FileText, Mail, MapPin, Menu, Phone, Shield, TrendingUp, X,
} from "lucide-react";

const NAV = [
  { label: "Funcionalidades", href: "#features" },
  { label: "Precios", href: "#pricing" },
  { label: "Calendario DIAN", href: "#calendar" },
  { label: "Contacto", href: "#contact" },
];

const FEATURES = [
  {
    icon: <FileText size={24} className="text-brand-orange" />,
    title: "Facturas DIAN",
    desc: "Procesa XML/PDF de facturación electrónica. Extrae CUFE, IVA 19%/5%, retención, bases y genera Excel automáticamente.",
    tag: "✅ Disponible",
  },
  {
    icon: <ClipboardList size={24} className="text-blue-400" />,
    title: "Exógenas Formato 1003",
    desc: "Carga certificados de retención en la fuente. Detecta múltiples conceptos por PDF, valida tasas y genera el Formato 1003 DIAN.",
    tag: "✅ Disponible",
  },
  {
    icon: <Calculator size={24} className="text-amber-400" />,
    title: "Liquidación de Nómina",
    desc: "Nómina mensual con parafiscales completos (SENA, ICBF, Caja), ARL por clase de riesgo, y liquidación definitiva CST Colombia 2026.",
    tag: "✅ Disponible",
  },
  {
    icon: <Bot size={24} className="text-violet-400" />,
    title: "Asistente IA Contable",
    desc: "Chatbot especializado en normativa DIAN, ET colombiano, IVA, retención, nómina y exógenas. Responde sobre tus propios documentos.",
    tag: "✅ Disponible",
  },
  {
    icon: <Shield size={24} className="text-emerald-400" />,
    title: "Deduplicación por CUFE",
    desc: "Cada factura se identifica por su CUFE único. Si vuelves a cargar la misma, no se duplica: el sistema la reconoce y la omite automáticamente.",
    tag: "✅ Disponible",
  },
  {
    icon: <Bell size={24} className="text-red-400" />,
    title: "Alertas DIAN",
    desc: "Calendario tributario con fechas clave 2026. Sincronización con Google Calendar y correo. Alertas antes de cada vencimiento.",
    tag: "🚧 Próximamente",
  },
  {
    icon: <Calendar size={24} className="text-cyan-400" />,
    title: "Calendario Tributario",
    desc: "Fechas DIAN 2026: retención mensual, IVA bimestral, renta personas jurídicas y naturales, exógenas y más.",
    tag: "✅ Disponible",
  },
  {
    icon: <Shield size={24} className="text-brand-orange" />,
    title: "Multi-empresa",
    desc: "Gestiona múltiples empresas o clientes desde una sola cuenta. Control de acceso por roles: dueño, admin, contador.",
    tag: "✅ Disponible",
  },
  {
    icon: <Download size={24} className="text-green-400" />,
    title: "Exportación Excel",
    desc: "Descarga reportes formateados en Excel: facturas procesadas, base de exógenas, nómina mensual y liquidaciones.",
    tag: "✅ Disponible",
  },
  {
    icon: <TrendingUp size={24} className="text-rose-400" />,
    title: "Declaración de Renta",
    desc: "Expediente digital por contribuyente. Carga documentos, aplica Art. 241 ET 2025 con tabla progresiva UVT y liquida renta personas naturales automáticamente.",
    tag: "✅ Disponible",
  },
];

const PLANS = [
  {
    name: "Gratuito",
    price: "$0",
    period: "/mes",
    desc: "Para conocer la herramienta",
    color: "border-gray-200",
    badge: null,
    features: [
      "50 facturas/mes",
      "10 certificados exógenas",
      "2 liquidaciones de nómina",
      "Exportación Excel",
      "1 usuario",
      "Soporte comunidad",
    ],
    noFeatures: ["Chatbot IA", "Calendario DIAN + alertas", "Multi-empresa", "API acceso"],
    cta: "Empezar gratis",
    href: "/login",
    primary: false,
  },
  {
    name: "Profesional",
    price: "$79.900",
    period: "/mes",
    desc: "Para contadores y firmas pequeñas",
    color: "border-brand-orange",
    badge: "Más popular",
    features: [
      "Facturas ilimitadas",
      "Exógenas ilimitadas",
      "Nómina ilimitada",
      "Chatbot IA contable",
      "Calendario DIAN + alertas",
      "Sincronización Google Calendar",
      "Hasta 5 usuarios",
      "Soporte por email 48h",
    ],
    noFeatures: ["API acceso", "Soporte prioritario"],
    cta: "Empezar 14 días gratis",
    href: "/login",
    primary: true,
  },
  {
    name: "Empresarial",
    price: "$249.900",
    period: "/mes",
    desc: "Para firmas y medianas empresas",
    color: "border-violet-500",
    badge: "Próximamente",
    features: [
      "Todo en Profesional",
      "Usuarios ilimitados",
      "API REST acceso completo",
      "Integraciones ERP (SIIGO, Helisa)",
      "Onboarding personalizado",
      "Soporte prioritario 4h",
      "Facturación electrónica DIAN",
    ],
    noFeatures: [],
    cta: "Contactar ventas",
    href: "#contact",
    primary: false,
  },
];

// Tomadas de api/data/calendario_2026.json, que es la fuente de verdad del calendario en la app.
// Las que había antes (May 20, Jun 16, Jun 30, Jul 20, Ago 18) ya estaban VENCIDAS y se mostraban
// como próximas: una landing que anuncia fechas pasadas resta credibilidad justo donde más
// importa. DEUDA: esto se vuelve a poner viejo solo; lo correcto es leerlas del JSON en build
// time — queda anotado en context/current-task.md.
const DIAN_PREVIEW = [
  { mes: "Sep", dia: 22, titulo: "Retención — agosto 2026", tipo: "retencion" },
  { mes: "Sep", dia: 22, titulo: "IVA bimestral — jul-ago", tipo: "iva" },
  { mes: "Sep", dia: 22, titulo: "Patrimonio — cuota 2", tipo: "patrimonio" },
  { mes: "Oct", dia: 23, titulo: "Retención — septiembre 2026", tipo: "retencion" },
  { mes: "Oct", dia: 23, titulo: "Renta personas naturales — cierre", tipo: "renta" },
  { mes: "Nov", dia: 25, titulo: "IVA bimestral — sep-oct", tipo: "iva" },
];

const TYPE_COLORS: Record<string, string> = {
  retencion: "text-brand-orange",
  iva: "text-sky-400",
  exogenas: "text-violet-400",
  renta: "text-rose-400",
  patrimonio: "text-amber-400",
};

// Lo que el pipeline revisa antes de entregar el Excel. Todo verificable en el código:
// pipeline/validator.py, pipeline/prorateo.py y pipeline/autorretenedores.txt.
const VALIDACIONES = [
  { k: "cufe", t: "Formato de CUFE y CUDE", d: "96 caracteres hexadecimales. Si no cuadra, no pasa." },
  { k: "dup", t: "Duplicados por CUFE", d: "La misma factura cargada dos veces no se cuenta dos veces." },
  { k: "suma", t: "Subtotal + IVA ≈ total", d: "Tolerancia de $1 COP. Detecta el descuadre de centavos." },
  { k: "490", t: "Prorrateo Art. 490 ET", d: "Mandatos siempre a no deducible; notas crédito restan del mes." },
  { k: "auto", t: "3.286 autorretenedores", d: "Listado DIAN cargado: reconoce al emisor automáticamente." },
  { k: "doc", t: "Tipos de documento", d: "Notas crédito y débito, doc. equivalente POS y SPD, mandato, peaje." },
];

// Ejemplo ilustrativo de una corrida — NO son cifras de uso del producto.
const LOG_PROCESO = [
  { t: "00:00", tag: "leer", c: "text-slate-500", m: "312 archivos (287 XML · 25 PDF)" },
  { t: "00:04", tag: "extraer", c: "text-slate-500", m: "CUFE, emisor, bases, IVA, retención" },
  { t: "00:11", tag: "validar", c: "text-slate-500", m: "subtotal + IVA ≈ total · tolerancia $1" },
  { t: "00:14", tag: "alerta", c: "text-amber-400", m: "4 facturas con inconsistencia — marcadas" },
  { t: "00:16", tag: "prorrateo", c: "text-slate-500", m: "Art. 490 ET aplicado a 2 períodos" },
  { t: "00:18", tag: "listo", c: "text-emerald-400", m: "BASE_DATOS.xlsx · VALIDACION · PRORRATEO_IVA" },
];

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [billingAnnual, setBillingAnnual] = useState(false);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMenuOpen(false);
  }

  return (
    <div className="bg-[#0b1220] text-slate-200 min-h-screen font-sans">
      {/* ── NAVBAR ─────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0b1220]/90 backdrop-blur border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 bg-brand-orange rounded-sm" />
            <span className="font-mono text-base font-semibold tracking-tight text-white">taxops</span>
          </div>

          <div className="hidden md:flex items-center gap-6">
            {NAV.map((n) => (
              <button key={n.label} onClick={() => scrollTo(n.href.slice(1))}
                className="font-mono text-xs text-slate-400 hover:text-brand-orange transition-colors">
                {n.label.toLowerCase()}
              </button>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link href="/login" className="text-sm text-slate-300 hover:text-white transition-colors px-3 py-2">
              Iniciar sesión
            </Link>
            <Link href="/signup"
              className="bg-brand-orange text-[#0b1220] text-sm font-bold px-5 py-2 rounded-lg hover:bg-orange-400 transition-colors">
              Empezar gratis
            </Link>
          </div>

          <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden p-2 text-slate-300" aria-label="Menú">
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {menuOpen && (
          <div className="md:hidden bg-[#0b1220] border-t border-slate-800 px-4 py-4 space-y-3">
            {NAV.map((n) => (
              <button key={n.label} onClick={() => scrollTo(n.href.slice(1))}
                className="block w-full text-left text-sm text-slate-300 py-2">
                {n.label}
              </button>
            ))}
            <Link href="/login" className="block text-sm text-slate-300 py-2">Iniciar sesión</Link>
            <Link href="/signup"
              className="block text-center bg-brand-orange text-[#0b1220] font-bold py-2.5 rounded-lg mt-2">
              Empezar gratis
            </Link>
          </div>
        )}
      </nav>

      {/* ── HERO ───────────────────────────────────────────────────────── */}
      <section className="pt-32 pb-12">
        <div className="max-w-6xl mx-auto px-4">
          <p className="font-mono text-xs text-brand-orange mb-5">$ taxops procesar ./facturas --mes 2026-09</p>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-[1.08] text-white mb-5 max-w-3xl text-pretty">
            El cierre mensual,<br />hecho por una máquina<br />que sabe el Estatuto.
          </h1>
          <p className="text-base text-slate-400 leading-relaxed mb-7 max-w-2xl">
            Subís los XML o PDF de tus facturas DIAN y sale un Excel con CUFE, bases, IVA y retención —
            con las inconsistencias ya marcadas. Lo mismo para exógenas, nómina y renta.
          </p>
          <div className="flex flex-wrap gap-3 items-center">
            <Link href="/signup"
              className="bg-brand-orange text-[#0b1220] font-bold px-6 py-3 rounded-lg hover:bg-orange-400 transition-colors">
              Empezar gratis
            </Link>
            <button onClick={() => scrollTo("features")}
              className="border border-slate-700 px-6 py-3 rounded-lg text-slate-200 hover:border-slate-500 transition-colors">
              Ver qué valida
            </button>
            <span className="text-xs text-slate-500">Sin tarjeta · 50 facturas al mes en el plan gratuito</span>
          </div>
        </div>
      </section>

      {/* ── LOG DE PROCESO ─────────────────────────────────────────────── */}
      <section className="pb-16">
        <div className="max-w-6xl mx-auto px-4">
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-5 font-mono text-xs leading-7 overflow-x-auto">
            {LOG_PROCESO.map((l) => (
              <div key={l.tag} className="flex gap-3 whitespace-nowrap">
                <span className="text-slate-600 w-14 shrink-0">{l.t}</span>
                <span className={`${l.c} w-20 shrink-0`}>{l.tag}</span>
                <span className="text-slate-300">{l.m}</span>
              </div>
            ))}
          </div>
          <p className="font-mono text-xs text-slate-600 mt-3">
            {/* Honestidad: es un ejemplo de corrida, no una métrica de uso del producto. */}
            {"// ejemplo de una corrida — cada paso queda registrado y es reproducible"}
          </p>
        </div>
      </section>

      {/* ── QUÉ VALIDA ─────────────────────────────────────────────────── */}
      <section className="border-t border-slate-800 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-2xl font-bold tracking-tight text-white mb-2">Lo que revisa antes de darte el Excel</h2>
          <p className="text-sm text-slate-400 mb-8">
            Los errores que un ojo humano deja pasar a las once de la noche del día 17.
          </p>
          <div className="grid md:grid-cols-2 gap-2.5">
            {VALIDACIONES.map((v) => (
              <div key={v.k} className="flex gap-3 p-4 bg-[#0f172a] rounded-lg border border-slate-800/80">
                <span className="font-mono text-[11px] text-brand-orange pt-0.5 shrink-0">{v.k}</span>
                <div>
                  <p className="text-sm font-semibold text-white mb-1">{v.t}</p>
                  <p className="text-xs text-slate-400 leading-relaxed">{v.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── MÓDULOS ────────────────────────────────────────────────────── */}
      <section id="features" className="border-t border-slate-800 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <p className="font-mono text-xs text-slate-600 mb-5">{"// módulos"}</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {FEATURES.map((f) => (
              <div key={f.title} className="p-4 bg-[#0f172a] rounded-lg border border-slate-800/80">
                <div className="flex items-center gap-2.5 mb-2">
                  {f.icon}
                  <span className="text-sm font-bold text-white">{f.title}</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed mb-3">{f.desc}</p>
                <span className={`font-mono text-[10px] ${f.tag.includes("Próximamente") ? "text-amber-400" : "text-emerald-400"}`}>
                  {f.tag.includes("Próximamente") ? "en curso" : "activo"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CALENDARIO ─────────────────────────────────────────────────── */}
      <section id="calendar" className="border-t border-slate-800 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-6">
            <h2 className="text-xl font-bold tracking-tight text-white">Calendario DIAN 2026</h2>
            <span className="font-mono text-xs text-slate-500">31 fechas cargadas</span>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {DIAN_PREVIEW.map((d) => (
              <div key={`${d.mes}-${d.dia}-${d.titulo}`} className="bg-[#0f172a] border border-slate-800/80 rounded-lg p-4">
                <p className={`font-mono text-[11px] mb-1.5 ${TYPE_COLORS[d.tipo] ?? "text-slate-400"}`}>
                  {d.dia} {d.mes.toUpperCase()}
                </p>
                <p className="text-xs font-semibold text-white leading-snug">{d.titulo}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PRECIOS ────────────────────────────────────────────────────── */}
      <section id="pricing" className="border-t border-slate-800 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3 mb-6">
            <h2 className="text-xl font-bold tracking-tight text-white">Precios</h2>
            <button onClick={() => setBillingAnnual(!billingAnnual)}
              className="font-mono text-xs text-slate-400 hover:text-brand-orange transition-colors">
              {billingAnnual ? "ver mensual" : "ver anual (−20%)"}
            </button>
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            {PLANS.map((plan) => (
              <div key={plan.name}
                className={`bg-[#0f172a] rounded-xl p-5 border ${plan.primary ? "border-brand-orange" : "border-slate-800"}`}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-bold text-white">{plan.name}</p>
                  {plan.badge && (
                    <span className="font-mono text-[10px] text-slate-500">{plan.badge.toLowerCase()}</span>
                  )}
                </div>
                <p className="font-mono text-2xl font-semibold text-white">
                  {plan.price}
                  <span className="text-xs text-slate-500 font-normal">{plan.period}</span>
                </p>
                <p className="text-[11px] text-slate-500 mt-1 mb-4">{plan.desc}</p>
                <Link href={plan.href}
                  className={`block text-center text-sm font-bold py-2.5 rounded-lg mb-4 transition-colors ${
                    plan.primary
                      ? "bg-brand-orange text-[#0b1220] hover:bg-orange-400"
                      : "border border-slate-700 text-slate-200 hover:border-slate-500"
                  }`}>
                  {plan.cta}
                </Link>
                <ul className="space-y-1.5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex gap-2 text-xs text-slate-300">
                      <Check size={13} className="text-emerald-400 shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                  {plan.noFeatures.map((f) => (
                    <li key={f} className="flex gap-2 text-xs text-slate-600">
                      <X size={13} className="shrink-0 mt-0.5" />
                      <span className="line-through">{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CIERRE HONESTO ─────────────────────────────────────────────── */}
      <section className="border-t border-slate-800 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-6">
            <h2 className="text-base font-bold text-white mb-2">TaxOps es un producto joven</h2>
            <p className="text-sm text-slate-400 leading-relaxed mb-5 max-w-2xl">
              No vamos a inventarte cifras de uso ni testimonios. Los módulos de facturas, exógenas, nómina,
              renta y calendario están funcionando hoy; podés probarlos gratis y juzgar vos. Si algo no sirve
              para tu caso, escribinos y lo hablamos.
            </p>
            <div className="flex flex-wrap gap-3 items-center">
              <Link href="/signup"
                className="bg-brand-orange text-[#0b1220] font-bold px-5 py-2.5 rounded-lg text-sm hover:bg-orange-400 transition-colors">
                Crear cuenta gratis
              </Link>
              <span className="font-mono text-xs text-slate-500">hola@taxops.co · Medellín</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── CONTACTO ───────────────────────────────────────────────────── */}
      <section id="contact" className="border-t border-slate-800 py-16">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-xl font-bold tracking-tight text-white mb-2">¿Tienes preguntas?</h2>
          <p className="text-sm text-slate-400 mb-8">Escríbenos y respondemos en menos de 24 horas.</p>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="space-y-5">
              {[
                { icon: <Mail size={18} className="text-brand-orange" />, label: "Email", value: "hola@taxops.co" },
                { icon: <Phone size={18} className="text-brand-orange" />, label: "WhatsApp", value: "+57 300 000 0000" },
                { icon: <MapPin size={18} className="text-brand-orange" />, label: "Ciudad", value: "Medellín, Colombia" },
              ].map((c) => (
                <div key={c.label} className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-[#0f172a] border border-slate-800 rounded-lg flex items-center justify-center shrink-0">
                    {c.icon}
                  </div>
                  <div>
                    <p className="font-mono text-[10px] text-slate-500">{c.label.toLowerCase()}</p>
                    <p className="text-sm font-semibold text-white">{c.value}</p>
                  </div>
                </div>
              ))}

              <div className="pt-2">
                <p className="text-sm text-slate-300 font-medium mb-2">¿Eres contador o firma contable?</p>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Pregúntanos sobre onboarding personalizado, migración de datos y planes para grupos de profesionales.
                </p>
              </div>
            </div>

            <form className="space-y-3" onSubmit={(e) => e.preventDefault()}>
              <div>
                <label htmlFor="c-nombre" className="block font-mono text-[10px] text-slate-500 mb-1">nombre</label>
                <input id="c-nombre"
                  className="w-full bg-[#0f172a] border border-slate-800 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-orange focus:border-transparent"
                  placeholder="Tu nombre" />
              </div>
              <div>
                <label htmlFor="c-email" className="block font-mono text-[10px] text-slate-500 mb-1">email</label>
                <input id="c-email" type="email"
                  className="w-full bg-[#0f172a] border border-slate-800 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-orange focus:border-transparent"
                  placeholder="tu@email.com" />
              </div>
              <div>
                <label htmlFor="c-msg" className="block font-mono text-[10px] text-slate-500 mb-1">mensaje</label>
                <textarea id="c-msg" rows={4}
                  className="w-full bg-[#0f172a] border border-slate-800 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 resize-none focus:outline-none focus:ring-2 focus:ring-brand-orange focus:border-transparent"
                  placeholder="¿En qué podemos ayudarte?" />
              </div>
              <button className="w-full bg-brand-orange text-[#0b1220] font-bold py-2.5 rounded-lg hover:bg-orange-400 transition-colors text-sm">
                Enviar mensaje
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* ── FOOTER ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-800 py-8">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4 font-mono text-[11px] text-slate-600">
          <span>taxops · automatización contable para Colombia</span>
          <div className="flex flex-wrap gap-5">
            <button onClick={() => scrollTo("features")} className="hover:text-slate-300 transition-colors">módulos</button>
            <button onClick={() => scrollTo("pricing")} className="hover:text-slate-300 transition-colors">precios</button>
            <button onClick={() => scrollTo("calendar")} className="hover:text-slate-300 transition-colors">calendario</button>
            <button onClick={() => scrollTo("contact")} className="hover:text-slate-300 transition-colors">contacto</button>
            <Link href="/login" className="hover:text-slate-300 transition-colors">entrar</Link>
          </div>
          <span>© 2026</span>
        </div>
      </footer>
    </div>
  );
}
