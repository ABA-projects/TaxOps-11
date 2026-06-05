# Renta UX — Onboarding + 4 mejoras

**Goal:** Mejorar la experiencia del módulo Renta con un onboarding visual y 4 correcciones de UX detectadas en pruebas.

**Scope:** Un único archivo `taxops-web/app/(app)/renta/page.tsx` (1328 líneas). Sin cambios de API ni DB.

---

## Cambios

### 1. Onboarding — Grid 4 pasos
- **Trigger:** `contribuyentes.length === 0 && !loading` O `!selected`
- **Contenido:** Grid 2×2 con tarjetas: Agregar (naranja), Cargar docs (verde), Calcular (azul), Exportar F210 (violeta)
- **CTA:** Botón "+ Agregar primer contribuyente" que llama `setShowForm(true)`
- **Ubicación:** Reemplaza el empty state actual del panel derecho (el `<div>` con `FileText size={48}`)

### 2. Descargas PDF/Excel con feedback
- **Estado:** `pdfLoading: boolean`, `xlsxLoading: boolean`, `downloadError: string | null`
- **Loading:** Botón muestra spinner + "Generando…" y queda `disabled`
- **Error:** Banner rojo debajo de los botones con el mensaje. Se limpia al volver a intentar.
- **Timeout:** 30 segundos máximo antes de mostrar error genérico

### 3. Botón duplicado eliminado
- Eliminar el `<button>` con texto "Recalcular con ajustes" (link underline, línea ~840)
- El botón principal "Recalcular" ya existe y funciona igual
- Agregar un chip `{Object.keys(overrides).length > 0 && <span>{n} ajuste{n>1?'s':''} manual{n>1?'es':''}</span>}` junto al botón principal

### 4. Info cards mejoradas + progress bar
- **Cards con color contextual:**
  - Documentos: verde si todos procesados, naranja si hay pendientes OCR
  - OCR pendientes: naranja si > 0, oculto si = 0
  - Saldo: azul con valor COP si hay declaración calculada, gris "Sin calcular" si no
  - Alertas: rojo si `inconsistencias.length > 0`, verde "Sin alertas" si = 0
- **Progress bar de 4 etapas** debajo de las cards: Cargado → OCR → Calculado → Exportado
  - Etapa activa = naranja, completada = verde, pendiente = gris

---

## Archivos afectados
- `taxops-web/app/(app)/renta/page.tsx` — único archivo modificado

## No incluido
- Cambios de API, DB, o rutas
- Refactoring del archivo
- Animaciones CSS complejas
