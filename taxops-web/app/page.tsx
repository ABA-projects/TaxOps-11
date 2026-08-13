"use client";

import Link from "next/link";
import { useState } from "react";
import {
  FileText, ClipboardList, Calculator, Bot, Zap, Shield,
  WifiOff, Bell, Calendar, ChevronRight, Check, Menu, X,
  Mail, Phone, MapPin, Star, TrendingUp, Download,
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
    tag: "🌐 Requiere internet",
  },
  {
    icon: <WifiOff size={24} className="text-emerald-400" />,
    title: "Funciona Sin Internet",
    desc: "Procesamiento de facturas, cálculos de nómina y exógenas funcionan 100% offline. Tus datos nunca salen de tu servidor.",
    tag: "🔒 Privacidad total",
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
      "SLA 99.9% uptime",
      "Facturación electrónica DIAN",
    ],
    noFeatures: [],
    cta: "Contactar ventas",
    href: "#contact",
    primary: false,
  },
];

const DIAN_PREVIEW = [
  { mes: "May", dia: 20, titulo: "Retención en la fuente", tipo: "retencion" },
  { mes: "Jun", dia: 16, titulo: "IVA bimestral mar-abr", tipo: "iva" },
  { mes: "Jun", dia: 30, titulo: "Exógenas 2025 – cierre", tipo: "exogenas" },
  { mes: "Jul", dia: 20, titulo: "Retención en la fuente", tipo: "retencion" },
  { mes: "Ago", dia: 18, titulo: "IVA bimestral may-jun", tipo: "iva" },
  { mes: "Oct", dia: 15, titulo: "Renta personas naturales", tipo: "renta" },
];

const TYPE_COLORS: Record<string, string> = {
  retencion: "bg-orange-500",
  iva: "bg-blue-500",
  exogenas: "bg-violet-500",
  renta: "bg-red-500",
};

const TESTIMONIALS = [
  { name: "Sandra M.", role: "Contadora pública · Medellín", text: "Antes me tomaba 3 horas procesar las facturas del mes. Con TaxOps son 20 minutos y el Excel ya está listo para el cliente." },
  { name: "Carlos R.", role: "Revisor fiscal · Bogotá", text: "El módulo de exógenas detectó 4 conceptos distintos en un mismo certificado. Antes los perdía." },
  { name: "Andrea T.", role: "Firma contable · Cali", text: "La calculadora de nómina con parafiscales nos ahorra 1 hora diaria. Y el chatbot resuelve dudas que antes tardábamos en buscar." },
];

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [billingAnnual, setBillingAnnual] = useState(false);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMenuOpen(false);
  }

  return (
    <div className="bg-white text-gray-900 min-h-screen font-sans">
      {/* ── NAVBAR ─────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur border-b border-gray-100 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="text-2xl font-black tracking-tight">
            <span className="text-brand-orange">Tax</span>
            <span className="text-brand-navy">Ops</span>
          </div>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            {NAV.map((n) => (
              <button key={n.label} onClick={() => scrollTo(n.href.slice(1))}
                className="text-sm text-gray-600 hover:text-brand-orange transition-colors font-medium">
                {n.label}
              </button>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link href="/login" className="text-sm font-semibold text-gray-700 hover:text-brand-orange transition-colors px-4 py-2">
              Iniciar sesión
            </Link>
            <Link href="/signup" className="bg-brand-orange text-white text-sm font-semibold px-5 py-2 rounded-xl hover:bg-orange-600 transition-colors">
              Empezar gratis →
            </Link>
          </div>

          {/* Mobile menu button */}
          <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden p-2 text-gray-600">
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {menuOpen && (
          <div className="md:hidden bg-white border-t border-gray-100 px-4 py-4 space-y-3">
            {NAV.map((n) => (
              <button key={n.label} onClick={() => scrollTo(n.href.slice(1))}
                className="block w-full text-left text-sm text-gray-700 py-2 font-medium">
                {n.label}
              </button>
            ))}
            <Link href="/signup" className="block w-full text-center bg-brand-orange text-white text-sm font-semibold px-5 py-2.5 rounded-xl mt-2">
              Empezar gratis →
            </Link>
          </div>
        )}
      </nav>

      {/* ── HERO ───────────────────────────────────────────────────────── */}
      <section className="pt-32 pb-20 bg-gradient-to-br from-slate-950 via-brand-navy to-slate-900 text-white">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-xs font-medium text-white/80 mb-6">
            <Zap size={12} className="text-brand-orange" />
            Funciona sin internet · Privacidad total · Hecho para Colombia
          </div>

          <h1 className="text-4xl md:text-6xl font-black leading-tight tracking-tight mb-6">
            Automatiza tu contabilidad<br />
            <span className="text-brand-orange">sin complicaciones</span>
          </h1>

          <p className="text-lg md:text-xl text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed">
            Procesa facturas electrónicas DIAN, genera exógenas Formato 1003, liquida nómina con todos los parafiscales
            y consulta el calendario tributario de Colombia — todo en una sola herramienta.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/signup"
              className="bg-brand-orange text-white font-bold px-8 py-4 rounded-2xl text-lg hover:bg-orange-600 transition-all hover:scale-105 shadow-lg shadow-orange-500/30">
              Empezar gratis
              <ChevronRight className="inline ml-1" size={20} />
            </Link>
            <button onClick={() => scrollTo("features")}
              className="border border-white/30 text-white font-semibold px-8 py-4 rounded-2xl text-lg hover:bg-white/10 transition-all">
              Ver funcionalidades
            </button>
          </div>

          <div className="mt-12 flex flex-wrap justify-center gap-8 text-sm text-slate-400">
            <span><strong className="text-white">+500</strong> facturas procesadas</span>
            <span><strong className="text-white">100%</strong> datos en tu servidor</span>
            <span><strong className="text-white">CST 2026</strong> actualizado</span>
            <span><strong className="text-white">0 instalación</strong> web app</span>
          </div>
        </div>
      </section>

      {/* ── CÓMO FUNCIONA ─────────────────────────────────────────────── */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-black text-brand-navy mb-3">Así de simple</h2>
          <p className="text-gray-500 mb-12">3 pasos y tienes tu reporte listo</p>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { n: "1", title: "Sube tus archivos", desc: "PDF o XML de facturas DIAN, certificados de retención. Arrastra y suelta o selecciona." },
              { n: "2", title: "TaxOps procesa", desc: "Extrae datos automáticamente: CUFE, IVA, bases, retención, conceptos. En segundos." },
              { n: "3", title: "Descarga el Excel", desc: "Reporte formateado y listo para presentar. También disponible para nómina y exógenas." },
            ].map((s) => (
              <div key={s.n} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 text-left">
                <div className="w-10 h-10 bg-brand-orange rounded-xl flex items-center justify-center text-white font-black text-lg mb-4">
                  {s.n}
                </div>
                <h3 className="font-bold text-gray-900 mb-2">{s.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ──────────────────────────────────────────────────── */}
      <section id="features" className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-black text-brand-navy mb-3">Todo lo que necesitas</h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              Una plataforma completa para la gestión tributaria y contable colombiana.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-gray-50 rounded-2xl p-6 border border-gray-100 hover:border-brand-orange hover:shadow-md transition-all group">
                <div className="mb-3">{f.icon}</div>
                <h3 className="font-bold text-gray-900 mb-2 group-hover:text-brand-orange transition-colors">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-3">{f.desc}</p>
                <span className="inline-block text-xs bg-white border border-gray-200 px-3 py-1 rounded-full text-gray-600 font-medium">
                  {f.tag}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── OFFLINE BADGE ─────────────────────────────────────────────── */}
      <section className="py-12 bg-brand-navy text-white">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-white/10 rounded-xl">
              <WifiOff size={28} className="text-brand-orange" />
            </div>
            <div>
              <h3 className="font-black text-xl mb-1">Funciona sin internet</h3>
              <p className="text-slate-300 text-sm">
                El procesamiento de facturas, cálculos de nómina y generación de exógenas son 100% locales.
                El chatbot IA y sincronización de calendario requieren conexión.
              </p>
            </div>
          </div>
          <div className="shrink-0">
            <Link href="/signup" className="bg-brand-orange text-white font-bold px-6 py-3 rounded-xl hover:bg-orange-600 transition-colors whitespace-nowrap">
              Probar ahora →
            </Link>
          </div>
        </div>
      </section>

      {/* ── CALENDAR PREVIEW ──────────────────────────────────────────── */}
      <section id="calendar" className="py-20 bg-gray-50">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-brand-navy mb-3">Calendario Tributario DIAN 2026</h2>
            <p className="text-gray-500 max-w-xl mx-auto">
              Nunca más pierdas una fecha. Retención, IVA, renta, exógenas y más — con alertas automáticas.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {DIAN_PREVIEW.map((e, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-start gap-3">
                <div className={`flex-shrink-0 w-12 h-12 rounded-xl ${TYPE_COLORS[e.tipo]} flex flex-col items-center justify-center text-white`}>
                  <span className="text-[10px] font-bold uppercase">{e.mes}</span>
                  <span className="text-lg font-black leading-none">{e.dia}</span>
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">{e.titulo}</p>
                  <p className="text-xs text-gray-400 mt-0.5 capitalize">{e.tipo.replace("_", " ")}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="text-center">
            <Link href="/login"
              className="inline-flex items-center gap-2 bg-brand-navy text-white font-semibold px-6 py-3 rounded-xl hover:bg-brand-navy/80 transition-colors">
              <Calendar size={16} />
              Ver calendario completo →
            </Link>
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ──────────────────────────────────────────────── */}
      <section className="py-20 bg-white">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-brand-navy mb-3">Lo que dicen los contadores</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
                <div className="flex gap-0.5 mb-3">
                  {[1,2,3,4,5].map((s) => <Star key={s} size={14} className="text-brand-orange fill-brand-orange" />)}
                </div>
                <p className="text-sm text-gray-700 leading-relaxed mb-4">&ldquo;{t.text}&rdquo;</p>
                <div>
                  <p className="font-bold text-gray-900 text-sm">{t.name}</p>
                  <p className="text-xs text-gray-400">{t.role}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PRICING ───────────────────────────────────────────────────── */}
      <section id="pricing" className="py-20 bg-gray-50">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-brand-navy mb-3">Precios transparentes</h2>
            <p className="text-gray-500 mb-6">Empieza gratis, escala cuando lo necesites.</p>

            {/* Billing toggle */}
            <div className="inline-flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-4 py-2">
              <span className={`text-sm font-medium ${!billingAnnual ? "text-brand-orange" : "text-gray-400"}`}>Mensual</span>
              <button
                onClick={() => setBillingAnnual(!billingAnnual)}
                className={`relative w-10 h-5 rounded-full transition-colors ${billingAnnual ? "bg-brand-orange" : "bg-gray-200"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${billingAnnual ? "translate-x-5" : ""}`} />
              </button>
              <span className={`text-sm font-medium ${billingAnnual ? "text-brand-orange" : "text-gray-400"}`}>
                Anual <span className="text-emerald-600 font-bold">−20%</span>
              </span>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {PLANS.map((p) => {
              const displayPrice = billingAnnual && p.price !== "$0"
                ? `$${Math.round(parseInt(p.price.replace(/\D/g, "")) * 0.8).toLocaleString("es-CO")}`
                : p.price;

              return (
                <div key={p.name} className={`bg-white rounded-2xl border-2 ${p.color} ${p.primary ? "shadow-xl shadow-orange-100" : "shadow-sm"} p-6 relative`}>
                  {p.badge && (
                    <div className={`absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-bold px-3 py-1 rounded-full ${p.primary ? "bg-brand-orange text-white" : "bg-violet-100 text-violet-700"}`}>
                      {p.badge}
                    </div>
                  )}

                  <div className="mb-4">
                    <h3 className="font-black text-gray-900 text-lg">{p.name}</h3>
                    <p className="text-xs text-gray-400 mb-3">{p.desc}</p>
                    <div className="flex items-end gap-1">
                      <span className="text-3xl font-black text-gray-900">{displayPrice}</span>
                      <span className="text-gray-400 text-sm mb-1">{p.period}</span>
                    </div>
                    {billingAnnual && p.price !== "$0" && (
                      <p className="text-xs text-emerald-600 mt-1">Facturado anualmente</p>
                    )}
                  </div>

                  <Link href={p.href}
                    className={`block w-full text-center py-2.5 rounded-xl font-semibold text-sm mb-5 transition-all ${
                      p.primary
                        ? "bg-brand-orange text-white hover:bg-orange-600"
                        : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                    }`}>
                    {p.cta}
                  </Link>

                  <ul className="space-y-2">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm text-gray-700">
                        <Check size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                        {f}
                      </li>
                    ))}
                    {p.noFeatures.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm text-gray-400">
                        <X size={14} className="mt-0.5 shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── CTA FINAL ─────────────────────────────────────────────────── */}
      <section className="py-20 bg-gradient-to-br from-brand-navy to-slate-900 text-white text-center">
        <div className="max-w-3xl mx-auto px-4">
          <TrendingUp size={40} className="text-brand-orange mx-auto mb-4" />
          <h2 className="text-3xl md:text-4xl font-black mb-4">
            Tu despacho merece herramientas del siglo XXI
          </h2>
          <p className="text-slate-300 text-lg mb-8">
            Únete a los contadores que ya automatizan su flujo de trabajo con TaxOps.
            Empieza gratis — sin tarjeta de crédito.
          </p>
          <Link href="/login"
            className="bg-brand-orange text-white font-bold px-10 py-4 rounded-2xl text-lg hover:bg-orange-600 transition-all hover:scale-105 shadow-lg shadow-orange-500/30 inline-block">
            Crear cuenta gratis →
          </Link>
        </div>
      </section>

      {/* ── CONTACT ───────────────────────────────────────────────────── */}
      <section id="contact" className="py-20 bg-white">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-brand-navy mb-3">¿Tienes preguntas?</h2>
            <p className="text-gray-500">Escríbenos y respondemos en menos de 24 horas.</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="space-y-6">
              {[
                { icon: <Mail size={20} className="text-brand-orange" />, label: "Email", value: "hola@taxops.co" },
                { icon: <Phone size={20} className="text-brand-orange" />, label: "WhatsApp", value: "+57 300 000 0000" },
                { icon: <MapPin size={20} className="text-brand-orange" />, label: "Ciudad", value: "Medellín, Colombia" },
              ].map((c) => (
                <div key={c.label} className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-orange-50 rounded-xl flex items-center justify-center shrink-0">{c.icon}</div>
                  <div>
                    <p className="text-xs text-gray-400">{c.label}</p>
                    <p className="font-semibold text-gray-900">{c.value}</p>
                  </div>
                </div>
              ))}

              <div className="pt-4">
                <p className="text-sm text-gray-500 font-medium mb-3">¿Eres contador o firma contable?</p>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Pregúntanos sobre onboarding personalizado, migración de datos y planes para grupos de profesionales.
                </p>
              </div>
            </div>

            <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nombre</label>
                <input className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange" placeholder="Tu nombre" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Email</label>
                <input type="email" className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange" placeholder="tu@email.com" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Mensaje</label>
                <textarea rows={4} className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange resize-none" placeholder="¿En qué podemos ayudarte?" />
              </div>
              <button className="w-full bg-brand-orange text-white font-semibold py-2.5 rounded-xl hover:bg-orange-600 transition-colors text-sm">
                Enviar mensaje
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────────── */}
      <footer className="bg-slate-950 text-slate-400 py-10 text-sm">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <span className="text-2xl font-black"><span className="text-brand-orange">Tax</span><span className="text-white">Ops</span></span>
            <p className="mt-1 text-xs">Automatización contable para Colombia · 2026</p>
          </div>
          <div className="flex flex-wrap gap-6 text-xs">
            <button onClick={() => scrollTo("features")} className="hover:text-white transition-colors">Funcionalidades</button>
            <button onClick={() => scrollTo("pricing")} className="hover:text-white transition-colors">Precios</button>
            <button onClick={() => scrollTo("calendar")} className="hover:text-white transition-colors">Calendario DIAN</button>
            <button onClick={() => scrollTo("contact")} className="hover:text-white transition-colors">Contacto</button>
            <Link href="/login" className="hover:text-white transition-colors">Iniciar sesión</Link>
          </div>
          <p className="text-xs">© 2026 TaxOps · Todos los derechos reservados</p>
        </div>
      </footer>
    </div>
  );
}

