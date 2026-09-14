import Link from "next/link";
import "./landing.css";
import FlujoXmlExcel from "@/components/landing/FlujoXmlExcel";
import { diaYMes, leerCalendarioDelRepo, proximosEventos } from "@/lib/calendarioPreview";

// Landing pública. Componente de servidor: el calendario se lee del JSON del repo en build time,
// así las fechas nunca vuelven a quedar vencidas en producción (deuda del PR #52).
// Todo el copy es verificable contra el producto: sin cifras de uso ni testimonios inventados.

// ISR diario: las fechas del calendario avanzan solas sin necesidad de un deploy.
export const revalidate = 86400;

const NAV = [
  { label: "Módulos", href: "#modulos" },
  { label: "Qué valida", href: "#valida" },
  { label: "Calendario DIAN", href: "#calendario" },
  { label: "Planes", href: "#planes" },
  { label: "Contacto", href: "#contacto" },
];

const DOLORES = [
  {
    dia: "día 3",
    t: "Bajar facturas una por una del catálogo DIAN",
    p: "Buscar, abrir, descargar, renombrar. Doscientas veces. Y al final una se te queda y aparece en la revisión.",
    fix: "Sueltas la carpeta de XML y ya está.",
  },
  {
    dia: "día 12",
    t: "Digitar bases y IVA desde el PDF",
    p: "El total no cuadra con la suma. ¿Es un descuento, un redondeo o un error tuyo? Lo revisas dos veces.",
    fix: "Se lee del XML, no del PDF: la cifra es la que firmó la DIAN.",
  },
  {
    dia: "día 17",
    t: "Recordar qué vence hoy según el último dígito del NIT",
    p: "Retención, IVA bimestral, exógenas. Cada cliente con su fecha. Una que se pasa es una sanción.",
    fix: "Calendario 2026 con alerta antes de cada vencimiento.",
  },
];

// Lo que el pipeline revisa antes de entregar el Excel. Todo verificable en pipeline/validator.py.
const CHECKS = [
  { t: "Formato de CUFE y CUDE", d: "96 caracteres hexadecimales. Si no cuadra, no pasa." },
  { t: "Duplicados por CUFE", d: "La misma factura cargada dos veces no se cuenta dos veces." },
  { t: "Subtotal + IVA ≈ total", d: "Tolerancia de $1 COP. Detecta el descuadre de centavos." },
  { t: "Prorrateo Art. 490 ET", d: "Mandatos siempre a no deducible; notas crédito restan del mes." },
  { t: "3.286 autorretenedores", d: "Listado DIAN cargado: reconoce al emisor automáticamente." },
  { t: "Tipos de documento", d: "Notas crédito y débito, doc. equivalente POS y SPD, mandato, peaje." },
];

const PLANES = [
  {
    name: "Gratuito",
    price: "$0",
    desc: "Para conocer la herramienta",
    badge: null,
    features: ["50 facturas/mes", "10 certificados exógenas", "2 liquidaciones de nómina", "Exportación Excel", "1 usuario"],
    no: ["Asistente IA", "Calendario DIAN + alertas", "Multi-empresa"],
    cta: "Empezar gratis",
    href: "/signup",
    primary: false,
  },
  {
    name: "Profesional",
    price: "$79.900",
    desc: "Para contadores y firmas pequeñas",
    badge: "Más popular",
    features: [
      "Facturas ilimitadas",
      "Exógenas ilimitadas",
      "Nómina ilimitada",
      "Asistente IA contable",
      "Calendario DIAN + alertas",
      "Sincronización Google Calendar",
      "Hasta 5 usuarios",
      "Soporte por email 48 h",
    ],
    no: [],
    cta: "Empezar 14 días gratis",
    href: "/signup",
    primary: true,
  },
  {
    name: "Empresarial",
    price: "$249.900",
    desc: "Para firmas y medianas empresas",
    badge: "Próximamente",
    features: [
      "Todo en Profesional",
      "Usuarios ilimitados",
      "API REST completa",
      "Integraciones ERP (Siigo, Helisa)",
      "Onboarding personalizado",
      "Soporte prioritario 4 h",
    ],
    no: [],
    cta: "Contactar ventas",
    href: "#contacto",
    primary: false,
  },
];

const TIPO_LABEL: Record<string, string> = {
  retencion: "Retención",
  iva: "IVA",
  exogenas: "Exógenas",
  renta: "Renta",
  patrimonio: "Patrimonio",
};

function Check() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M5 12l5 5L19 7" />
    </svg>
  );
}

export default function LandingPage() {
  const hoy = new Date().toISOString().slice(0, 10);
  const eventos = proximosEventos(leerCalendarioDelRepo(), hoy, 6);

  return (
    <div className="lp">
      <nav>
        <div className="wrap">
          <Link className="brand" href="/">
            <i />
            taxops
          </Link>
          <ul className="links">
            {NAV.map((n) => (
              <li key={n.href}>
                <a href={n.href}>{n.label}</a>
              </li>
            ))}
          </ul>
          <div className="nav-cta">
            <Link className="btn btn-ghost" href="/login">
              Iniciar sesión
            </Link>
            <Link className="btn btn-primary" href="/signup">
              Empezar gratis
            </Link>
            <details className="menu">
              <summary aria-label="Menú">☰</summary>
              <ul>
                {NAV.map((n) => (
                  <li key={n.href}>
                    <a href={n.href}>{n.label}</a>
                  </li>
                ))}
                <li>
                  <Link href="/login">Iniciar sesión</Link>
                </li>
              </ul>
            </details>
          </div>
        </div>
      </nav>

      <section className="hero">
        <div className="wrap">
          <div className="hero-copy">
            <span className="eyebrow">Automatización contable para Colombia</span>
            <h1>
              Tus facturas DIAN, en Excel y validadas. <em>Sin digitar.</em>
            </h1>
            <p className="lead">
              Subes los XML o PDF de tus facturas DIAN y sale un Excel con CUFE, bases, IVA y retención — con las
              inconsistencias ya marcadas. Lo mismo para exógenas, nómina y renta.
            </p>
            <div className="hero-actions">
              <Link className="btn btn-primary" href="/signup">
                Empezar gratis
              </Link>
              <a className="btn btn-ghost" href="#valida">
                Ver qué valida
              </a>
            </div>
            <p className="hero-note">Sin tarjeta · 50 facturas al mes en el plan gratuito</p>
          </div>
          <div className="frame" aria-label="Ejemplo del asistente contable">
            <div className="frame-bar">
              <b />
              <b />
              <b />
              <span>app.taxopsapp.com · asistente</span>
            </div>
            <div className="chat">
              <div className="msg u">¿Cuánto IVA descontable tengo en agosto y qué facturas quedaron con error?</div>
              <div className="tool">
                <i />
                consultar_iva_mes · resumen_errores
              </div>
              <div className="msg a">
                En <strong>agosto 2026</strong> tienes 47 facturas procesadas. El IVA descontable, después del prorrateo
                Art. 490 ET, queda así:
                <table className="mono">
                  <tbody>
                    <tr>
                      <td>IVA gravado 19 %</td>
                      <td>$ 4.812.300</td>
                    </tr>
                    <tr>
                      <td>IVA 5 %</td>
                      <td>$ 96.450</td>
                    </tr>
                    <tr>
                      <td>No deducible (mandatos)</td>
                      <td>− $ 312.000</td>
                    </tr>
                    <tr className="tot">
                      <td>Descontable</td>
                      <td>$ 4.596.750</td>
                    </tr>
                  </tbody>
                </table>
                <p style={{ marginTop: 10 }}>
                  4 facturas marcadas: 2 con CUFE duplicado, 1 con subtotal + IVA que no cuadra ($ 0,03) y 1 sin NIT del
                  adquiriente.
                </p>
              </div>
            </div>
            <div className="frame-foot">
              Conversación ilustrativa con cifras de ejemplo. Las herramientas que aparecen son las reales del asistente.
            </div>
          </div>
        </div>
      </section>

      <section className="demo" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="frame">
            <div className="frame-bar">
              <b />
              <b />
              <b />
              <span>del AttachedDocument de la DIAN al Excel del cierre</span>
            </div>
            <FlujoXmlExcel />
            <div className="frame-foot">
              Ilustración del flujo con cifras de ejemplo. El formato del XML y las validaciones son las reales.
            </div>
          </div>
        </div>
      </section>

      <section className="pains">
        <div className="wrap">
          <div>
            <span className="eyebrow">Si eres contador en Colombia</span>
            <h2 style={{ marginTop: 14 }}>Esto ya lo sabes. Nadie te lo tiene que explicar.</h2>
            <p className="lead" style={{ marginTop: 18 }}>
              Los errores que un ojo humano deja pasar a las once de la noche del día 17.
            </p>
          </div>
          <div className="pain-list">
            {DOLORES.map((d) => (
              <div className="pain" key={d.dia}>
                <time>{d.dia}</time>
                <div>
                  <h3>{d.t}</h3>
                  <p>{d.p}</p>
                  <p className="fix">{d.fix}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="modulos">
        <div className="wrap">
          <span className="eyebrow">Módulos</span>
          <h2 style={{ marginTop: 14, maxWidth: "22ch" }}>Cinco cosas que hace hoy, no en el roadmap.</h2>
          <div className="bento">
            <div className="tile big">
              <span className="k">FACTURAS · XML / PDF</span>
              <div className="tile-art">
                <span className="row ok" style={{ top: 16, width: "70%" }} />
                <span className="row ok" style={{ top: 36, width: "82%" }} />
                <span className="row warn" style={{ top: 56, width: "48%" }} />
                <span className="row ok" style={{ top: 76, width: "64%" }} />
                <span className="row ok" style={{ top: 96, width: "76%" }} />
              </div>
              <h3>Facturas DIAN</h3>
              <p>
                Procesa XML o PDF de facturación electrónica. Extrae CUFE, IVA 19 % / 5 %, retención y bases; genera el
                Excel con BASE_DATOS, VALIDACIÓN y PRORRATEO_IVA.
              </p>
            </div>
            <div className="tile">
              <span className="k">EXÓGENAS</span>
              <div className="stat">
                1003
                <small>Formato DIAN generado desde certificados PDF, imagen, Excel o Word</small>
              </div>
              <h3>Exógenas</h3>
              <p>Detecta varios conceptos por certificado y valida las tarifas.</p>
            </div>
            <div className="tile">
              <span className="k">DEDUPLICACIÓN</span>
              <div className="stat">
                96
                <small>caracteres de CUFE. Si vuelves a cargar la misma factura, se omite sola.</small>
              </div>
              <h3>Nunca dos veces</h3>
              <p>La misma factura cargada dos veces no se cuenta dos veces.</p>
            </div>
            <div className="tile">
              <span className="k">NÓMINA</span>
              <h3>Liquidación de nómina</h3>
              <p>
                Mensual con parafiscales completos (SENA, ICBF, Caja), ARL por clase de riesgo y liquidación definitiva
                CST 2026.
              </p>
            </div>
            <div className="tile">
              <span className="k">RENTA · PERSONAS NATURALES</span>
              <h3>Declaración de renta</h3>
              <p>Expediente por contribuyente, tabla progresiva UVT del Art. 241 ET y liquidación automática.</p>
            </div>
            <div className="tile">
              <span className="k">ASISTENTE</span>
              <h3>Asistente contable con IA</h3>
              <p>
                Responde sobre normativa DIAN, ET, IVA, retención y nómina — y sobre <strong>tus propios documentos</strong>,
                consultando la base real, no adivinando.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="checks" id="valida">
        <div className="wrap">
          <div>
            <span className="eyebrow">Qué valida</span>
            <h2 style={{ marginTop: 14 }}>Lo que revisa antes de darte el Excel.</h2>
            <p className="lead" style={{ marginTop: 18 }}>
              Todo esto está en el código y se puede leer. Ninguna es una promesa.
            </p>
          </div>
          <div className="check-grid">
            {CHECKS.map((c) => (
              <div className="check" key={c.t}>
                <Check />
                <div>
                  <b>{c.t}</b>
                  <span>{c.d}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="calendario">
        <div className="wrap">
          <div className="cal-head">
            <div>
              <span className="eyebrow">Calendario DIAN 2026</span>
              <h2 style={{ marginTop: 14 }}>Lo que vence próximamente.</h2>
            </div>
            <p className="hero-note">Fechas del calendario oficial 2026 · rangos por último dígito del NIT</p>
          </div>
          <div className="cal">
            {eventos.map((e) => {
              const { dia, mes } = diaYMes(e.fecha);
              return (
                <div className="ev" key={e.id}>
                  <div className="d">
                    <b>{dia}</b>
                    <small>{mes}</small>
                  </div>
                  <div>
                    <span className="tag">{TIPO_LABEL[e.tipo] ?? e.tipo}</span>
                    <h3>{e.titulo}</h3>
                    {e.articulo && <p>{e.articulo}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section id="planes" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <span className="eyebrow">Planes</span>
          <h2 style={{ marginTop: 14 }}>Empieza gratis. Paga cuando te ahorre tiempo.</h2>
          <div className="plans">
            {PLANES.map((p) => (
              <div className={p.primary ? "plan hi" : "plan"} key={p.name}>
                {p.badge && <span className={p.badge === "Próximamente" ? "badge soon" : "badge"}>{p.badge}</span>}
                <div>
                  <h3>{p.name}</h3>
                  <p style={{ color: "var(--muted)" }}>{p.desc}</p>
                </div>
                <div className="price">
                  {p.price}
                  <small> /mes</small>
                </div>
                <ul>
                  {p.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                  {p.no.map((f) => (
                    <li className="no" key={f}>
                      {f}
                    </li>
                  ))}
                </ul>
                {p.href.startsWith("#") ? (
                  <a className="btn btn-ghost" href={p.href}>
                    {p.cta}
                  </a>
                ) : (
                  <Link className={p.primary ? "btn btn-primary" : "btn btn-ghost"} href={p.href}>
                    {p.cta}
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="honest">
        <div className="wrap">
          <h2>TaxOps es un producto joven. No te vamos a vender humo.</h2>
          <div>
            <p>
              No inventamos cifras de uso ni testimonios. Los módulos de facturas, exógenas, nómina, renta y calendario
              funcionan hoy; puedes probarlos gratis y juzgar tú. Si algo no sirve para tu caso, escríbenos y lo
              hablamos.
            </p>
            <Link className="btn" href="/signup" style={{ marginTop: 22 }}>
              Crear cuenta gratis
            </Link>
          </div>
        </div>
      </section>

      <section className="contact" id="contacto">
        <div className="wrap">
          <div className="contact-info">
            <span className="eyebrow">Contacto</span>
            <h2>¿Eres contador o firma contable?</h2>
            <p className="lead">
              Pregúntanos sobre onboarding, migración de datos y planes para grupos de profesionales. Respondemos en
              menos de 24 horas.
            </p>
            <p className="mono">hola@taxops.co · Medellín</p>
          </div>
          {/* El formulario no tiene backend todavía (igual que antes de este rediseño): mailto para que al menos llegue. */}
          <form action="mailto:hola@taxops.co" method="post" encType="text/plain">
            <label htmlFor="c-nombre">
              Nombre
              <input id="c-nombre" name="nombre" type="text" placeholder="Tu nombre" />
            </label>
            <label htmlFor="c-email">
              Correo
              <input id="c-email" name="email" type="email" placeholder="tu@firma.com" />
            </label>
            <label htmlFor="c-msg">
              Mensaje
              <textarea
                id="c-msg"
                name="mensaje"
                placeholder="Cuéntanos cuántas facturas procesas al mes y qué te quita más tiempo."
              />
            </label>
            <button className="btn btn-primary" type="submit" style={{ justifySelf: "start" }}>
              Enviar mensaje
            </button>
          </form>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <span>taxops · automatización contable para Colombia</span>
          <span className="mono">Medellín · 2026</span>
        </div>
      </footer>
    </div>
  );
}
