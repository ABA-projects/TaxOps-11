// Ilustración del flujo real: AttachedDocument (XML DIAN) → TaxOps → hoja VALIDACIÓN.
// Cifras de ejemplo; el formato del XML y los estados de validación son los reales del pipeline.
export default function FlujoXmlExcel() {
  return (
    <svg className="flow" viewBox="0 0 1200 520" role="img" aria-label="Tres XML de la DIAN entran a TaxOps y salen como un Excel con la hoja VALIDACIÓN">
            <defs>
              <pattern id="rule" width="1200" height="28" patternUnits="userSpaceOnUse"><line x1="0" y1="27.5" x2="1200" y2="27.5" stroke="var(--rule)"/></pattern>
              <filter id="sh" x="-10%" y="-10%" width="130%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#17201c" floodOpacity=".12"/></filter>
            </defs>
            <rect width="1200" height="520" fill="var(--surface)"/>
            <rect width="1200" height="520" fill="url(#rule)"/>
                    <g fontFamily="JetBrains Mono,monospace" fontSize="13" fill="var(--muted)">
              <g transform="translate(80 150) rotate(-4)" filter="url(#sh)">
                <rect width="250" height="200" rx="12" fill="var(--surface)" stroke="var(--line)"/>
                <text x="18" y="34" fill="var(--accent)" fontWeight="500">&lt;AttachedDocument&gt;</text>
                <text x="30" y="60">&lt;cbc:ID&gt;FE-10482</text><text x="30" y="84">&lt;cac:Attachment&gt;</text>
                <text x="42" y="108">&lt;![CDATA[&lt;Invoice&gt;</text><text x="42" y="132" fill="var(--ink)">CUFE 8f3a…c19e</text>
                <text x="42" y="156">IVA 19 %  $ 812.300</text><text x="18" y="184" fill="var(--accent)" fontWeight="500">&lt;/AttachedDocument&gt;</text>
              </g>
              <g transform="translate(120 120) rotate(2)" filter="url(#sh)">
                <rect width="250" height="200" rx="12" fill="var(--surface)" stroke="var(--line)"/>
                <text x="18" y="34" fill="var(--accent)" fontWeight="500">&lt;AttachedDocument&gt;</text>
                <text x="30" y="60">&lt;cbc:ID&gt;NC-00217</text><text x="30" y="84">&lt;cac:Attachment&gt;</text>
                <text x="42" y="108">&lt;![CDATA[&lt;CreditNote&gt;</text><text x="42" y="132" fill="var(--ink)">CUDE 21bd…77a0</text>
                <text x="42" y="156">IVA 19 %  −$ 96.450</text><text x="18" y="184" fill="var(--accent)" fontWeight="500">&lt;/AttachedDocument&gt;</text>
              </g>
              <g transform="translate(160 90)" filter="url(#sh)">
                <rect width="250" height="200" rx="12" fill="var(--surface)" stroke="var(--line)"/>
                <text x="18" y="34" fill="var(--accent)" fontWeight="500">&lt;AttachedDocument&gt;</text>
                <text x="30" y="60">&lt;cbc:ID&gt;FE-10491</text><text x="30" y="84">&lt;cac:Attachment&gt;</text>
                <text x="42" y="108">&lt;![CDATA[&lt;Invoice&gt;</text><text x="42" y="132" fill="var(--ink)">CUFE e02c…4b51</text>
                <text x="42" y="156">IVA 19 %  $ 1.240.000</text><text x="18" y="184" fill="var(--accent)" fontWeight="500">&lt;/AttachedDocument&gt;</text>
              </g>
            </g>
                    <g transform="translate(500 200)">
              <circle cx="60" cy="60" r="58" fill="var(--accent)"/>
              <path d="M38 62l14 14 30-32" fill="none" stroke="var(--accent-ink)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"/>
              <text x="60" y="150" textAnchor="middle" fontFamily="Source Sans 3,sans-serif" fontSize="15" fill="var(--muted)">extrae · valida · prorratea</text>
            </g>
            <path d="M430 260 H495" stroke="var(--accent)" strokeWidth="3" strokeDasharray="6 6"/>
            <path d="M625 260 H690" stroke="var(--accent)" strokeWidth="3" strokeDasharray="6 6"/>
                    <g transform="translate(700 80)" filter="url(#sh)" fontFamily="JetBrains Mono,monospace" fontSize="13">
              <rect width="440" height="360" rx="14" fill="var(--surface)" stroke="var(--line)"/>
              <rect width="440" height="44" rx="14" fill="var(--accent-soft)"/><rect y="30" width="440" height="14" fill="var(--accent-soft)"/>
              <text x="18" y="28" fontFamily="Source Sans 3,sans-serif" fontWeight="600" fontSize="15" fill="var(--accent)">VALIDACIÓN.xlsx</text>
              <g fill="var(--muted)"><text x="18" y="76">FOLIO</text><text x="120" y="76">CUFE</text><text x="250" y="76">TOTAL</text><text x="360" y="76">ESTADO</text></g>
              <line x1="0" y1="88" x2="440" y2="88" stroke="var(--line)"/>
              <g fill="var(--ink)">
                <text x="18" y="118">FE-10482</text><text x="120" y="118">8f3a…c19e</text><text x="250" y="118">5.085.300</text><rect x="352" y="103" width="52" height="22" rx="11" fill="var(--accent-soft)"/><text x="378" y="118" textAnchor="middle" fill="var(--accent)" fontWeight="500">OK</text>
                <text x="18" y="158">NC-00217</text><text x="120" y="158">21bd…77a0</text><text x="250" y="158">−604.450</text><rect x="352" y="143" width="52" height="22" rx="11" fill="var(--accent-soft)"/><text x="378" y="158" textAnchor="middle" fill="var(--accent)" fontWeight="500">OK</text>
                <text x="18" y="198">FE-10491</text><text x="120" y="198">e02c…4b51</text><text x="250" y="198">7.764.000</text><rect x="352" y="183" width="52" height="22" rx="11" fill="var(--accent-soft)"/><text x="378" y="198" textAnchor="middle" fill="var(--accent)" fontWeight="500">OK</text>
                <text x="18" y="238">FE-10482</text><text x="120" y="238">8f3a…c19e</text><text x="250" y="238">5.085.300</text><rect x="338" y="223" width="80" height="22" rx="11" fill="var(--amber-soft)"/><text x="378" y="238" textAnchor="middle" fill="var(--amber)" fontWeight="500">DUPLICADO</text>
                <text x="18" y="278">FE-10503</text><text x="120" y="278">b7e1…90cd</text><text x="250" y="278">318.000</text><rect x="338" y="263" width="80" height="22" rx="11" fill="var(--amber-soft)"/><text x="378" y="278" textAnchor="middle" fill="var(--amber)" fontWeight="500">DESCUADRE</text>
              </g>
              <line x1="0" y1="300" x2="440" y2="300" stroke="var(--line)"/>
              <text x="18" y="332" fill="var(--muted)">IVA descontable (Art. 490)</text><text x="422" y="332" textAnchor="end" fill="var(--ink)" fontWeight="500">$ 4.596.750</text>
            </g>
          </svg>
  );
}
