# Fuentes del canvas de diseño de la landing

Artboards de las 3 direcciones exploradas para la landing de TaxOps, en formato `.dc.html`
(Claude Design canvas).

| Archivo | Dirección | Estado |
|---|---|---|
| `Herramienta.dc.html` | **C — "Herramienta"** (oscura, IBM Plex Mono, log de proceso) | **Elegida** por Jaime; es la que se porta a `taxops-web/app/page.tsx` |
| `Main.dc.html` | A — "Producto a la vista" | Descartada, se conserva como referencia |
| `Editorial.dc.html` | B — "Editorial tributario" | Descartada, se conserva como referencia |
| `canvas.json` | Layout del canvas + notas de tradeoffs | — |

Canvas publicado: https://claude.ai/code/artifact/66cbf36f-054d-478a-a17c-3bb8bfbd4d4b

**Por qué viven en el repo:** la primera vez estos fuentes solo existían en `/tmp`, se perdieron
con la limpieza del sistema, y el handoff llegó a darlos por irrecuperables. Sí se recuperan
—desde el artifact publicado— pero depende de una sesión autenticada de Claude. Versionarlos acá
quita esa dependencia: cualquiera (Kiro incluido) puede leerlos.
