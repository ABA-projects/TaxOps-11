# TaxOps - Design Brief Profesional

## Resumen Ejecutivo
Diseño de identidad visual para **TaxOps**, una startup SaaS de tecnología contable que fusiona DevOps con finanzas. El logo debe comunicar automatización, precisión y confianza en un diseño minimalista y escalable.

---

## 1. Concepto Visual Central

### Fusión DevOps + Finanzas
- **DevOps**: Automatización, pipelines, sistemas, eficiencia operativa
- **Finanzas**: Precisión, impuestos, datos estructurados, confianza

### Elementos Clave del Isotipo
```
┌─────────────────────────────────────────┐
│  ENGRANAJE (automatización) +           │
│  SÍMBOLO DE PORCENTAJE o GRID           │
│  (finanzas/precisión)                   │
│                                         │
│  → Integración abstracta y moderna      │
│  → Evitar literalidad                   │
│  → Alto impacto visual con detalle      │
└─────────────────────────────────────────┘
```

---

## 2. Paleta de Colores (ESTRICTA)

| Color | Código | Uso | Propósito |
|-------|--------|-----|-----------|
| **Naranja Vibrante** | `#E05519` | Elementos DevOps, energía, tech | Innovación, dinamismo |
| **Azul Marino** | `#1A1A2E` | Elementos Finanzas, texto "Tax" | Confianza, solidez, profesionalismo |
| **Blanco** | `#FFFFFF` | Fondo, espacios negativos | Limpieza, modernidad |
| **Gris Neutro** | `#F5F5F5` | Fondo alternativo | Accesibilidad |

### Contrastes
- Naranja sobre Azul: **Alto contraste** ✓
- Ambos sobre blanco: **Excelente legibilidad** ✓

---

## 3. Tipografía

### Requerimientos
- **Familia**: Sans serif geométrica, moderna (estilo SaaS)
- **Peso**: 600-700 (semibold a bold)
- **Opciones recomendadas**:
  - Montserrat
  - Inter
  - Poppins
  - Futura
  - DM Sans

### Implementación
```
┌──────────────────────────────┐
│  Tax    Ops                  │
│  #1A1A2E  #E05519            │
│  Azul     Naranja            │
│  (izq.)   (derecha)          │
└──────────────────────────────┘
```

### Kerning
- Espaciado natural, sin amontonamiento
- Alineación baseline clara
- Proporción de 2:1 entre ancho de "Tax" y "Ops" recomendado

---

## 4. Isotipo (Símbolo Puro)

### Especificaciones Técnicas

#### Tamaño Grid
- **Canvas**: 64 x 64 px (mínimo escalable)
- **Versión alta resolución**: 512 x 512 px o superior

#### Construcción Geométrica
```
Centro: (32, 32)
Radio externo engranaje: 28 px
Dientes: 8 dientes (simétricos)
Ancho línea: 2-2.5 px
```

#### Elementos

**A. Engranaje Central**
- 8 dientes regularmente espaciados
- Rotación: 45° respecto a símbolos internos
- Color: Naranja `#E05519`
- Estilo: Línea limpia (stroke, no relleno)

**B. Símbolo Interior**
Opción recomendada: **"% Grid Híbrido"**
- Porcentaje esquemático (2 círculos + línea diagonal)
- Superpuesto con grid de 3x3 células (líneas finas)
- Color: Azul marino `#1A1A2E`
- Opacidad: 100% (contraste total)

#### Versiones Requeridas

| Versión | Descripción | Uso |
|---------|-------------|-----|
| **Isotipo Principal** | Engranaje + símbolo (colores) | Brand principal |
| **Isotipo Monocromo Oscuro** | Negro o azul marino | Impresión, B&W |
| **Isotipo Monocromo Claro** | Blanco (para fondos oscuros) | Dark mode, overlays |
| **Isotipo Negativo** | Fondo naranja/azul, elemento blanco | Favicon, avatares |

---

## 5. Logotipo Horizontal

### Configuración de Layout

```
┌─────────────────────────────────────────┐
│  [ISOTIPO]    TaxOps                    │
│  (64x64 px)   Montserrat Bold           │
│               32px height (aprox.)      │
│                                         │
│  Espaciado: 16 px entre icon y texto    │
│  Altura total: ~80 px                   │
│  Ancho mínimo: 280 px                   │
└─────────────────────────────────────────┘
```

### Variaciones Soportadas

1. **Logo Horizontal Standard**
   - Icono + Texto "TaxOps"
   - Con espaciado de marca

2. **Logo Vertical**
   - Icono encima
   - Texto centrado debajo
   - Para aplicaciones móviles

3. **Logo Solo Isotipo**
   - Para favicon, app icon
   - Mínimo: 32x32 px
   - Óptimo: 256x256 px

---

## 6. Especificaciones Técnicas de Entrega

### Formatos Requeridos

| Formato | Uso | Notas |
|---------|-----|-------|
| **SVG** | Web, apps, escalable | Óptimo para todos usos |
| **PNG** | Web, redes sociales | Transparencia de fondo |
| **PDF** | Impresión, marca | Vector, compatible |
| **AI/PSD** | Diseño, edición futura | Formato nativo |
| **ICO** | Favicon | 16x16, 32x32, 64x64 |

### Directrices de Uso

#### Espacio Mínimo de Respiración (Clearspace)
```
┌─ Espacio mínimo = altura de "T" en TaxOps
│
│ [ISOTIPO]              MARGIN = altura /2
│           TaxOps
│
```

#### Tamaños Mínimos de Reproducción
- **Pantalla**: 48 x 48 px (como mínimo)
- **Impresión**: 25 mm x 25 mm
- **Favicon**: 32 x 32 px

#### Prohibiciones (Don'ts)
- ❌ Cambiar colores (usar paleta establecida)
- ❌ Estirar, deformar o rotar isotipo
- ❌ Agregar sombras, bordes o efectos 3D
- ❌ Combinar con otros logos o marcas
- ❌ Usar en fondos con bajo contraste
- ❌ Redimensionar texto independientemente del icono

---

## 7. Guía de Estilo Visual

### Principios de Diseño

**Minimalismo**
- Máximo 2 elementos principales (engranaje + símbolo)
- Líneas limpias, sin rellenos innecesarios
- Espacios negativos utilizados estratégicamente

**Modernidad & Tech**
- Flat design (sin texturas, gradientes sutiles en máximo)
- Inspirado en Stripe, Linear, Vercel, Notion
- Geométrico, simétrico, balanceado

**Escalabilidad**
- Debe verse igual a 16px que a 512px
- Stroke consistente (no pixelado)
- Líneas de espesor 2-3px

**Legibilidad**
- Alto contraste naranja/azul
- Tipografía clara en todos tamaños
- Proporción equilibrada entre icono y texto (1:1.5)

---

## 8. Inspiración & Referencias

### Startups SaaS Similares
- **Vercel**: Simplicidad, marca geométrica
- **Linear**: Minimalismo, tipografía limpia
- **Stripe**: Confianza a través de diseño simple
- **Retool**: Combinación de elementos técnicos
- **Figma**: Icono singular + texto limpio

### Elementos a Evitar
- ❌ Calculadoras obvias o gráficos stock
- ❌ Símbolos financieros genéricos (💰, 📊, 💹)
- ❌ Efectos 3D o sombras complejas
- ❌ Demasiados colores o degradados
- ❌ Tipografía decorativa o serif pesada

---

## 9. Implementación Digital

### Para Web
```html
<!-- Logo SVG inline -->
<svg class="taxops-logo" viewBox="0 0 256 80" xmlns="http://www.w3.org/2000/svg">
  <!-- Icono + Texto -->
</svg>

<!-- Favicon -->
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
```

### Para Apps
- **iOS**: SafeArea compatible, usar 64x64 como base
- **Android**: Respetar material design guidelines
- **Web**: SVG responsive con `max-width: 100%`

---

## 10. Checklist de Validación

- [ ] Isotipo reconocible a 32px y 512px
- [ ] Colores exactos: #E05519 y #1A1A2E
- [ ] Tipografía sans serif geométrica implementada
- [ ] Versiones monocromo funcionan en B&W
- [ ] Logo legible en fondos claros y oscuros
- [ ] SVG optimizado (sin paths innecesarios)
- [ ] PDF de alta resolución disponible
- [ ] Guía de marca documentada
- [ ] Favicon generado correctamente
- [ ] Cumple con estándares WCAG de accesibilidad

---

## 11. Próximos Pasos

1. **Validación**: Presentar concepto SVG para feedback
2. **Iteración**: Ajustes de proporciones, espaciado
3. **Refinamiento**: Detalles de stroke, kerning
4. **Exportación**: Generar formatos finales (SVG, PNG, PDF, ICO)
5. **Documentación**: Crear brand guidelines completo
6. **Implementación**: Integrar en web, apps, materiales

---

**Fecha**: Mayo 2026  
**Proyecto**: TaxOps - Brand Identity  
**Estado**: Design Brief - Listo para Diseño Ejecutivo
