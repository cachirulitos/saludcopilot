# TASK.md — apps/dashboard

> Read CLAUDE.md and ARQUITECTURA.md before starting.
> Build with mock data first (Task 3). Replace with live API
> only after Tasks 3, 4, and 7 in apps/api/TASK.md are complete.

---

## Current status

- [x] Project scaffold created
- [x] Next.js initialized with Tailwind v4 (light theme)
- [x] Layout: sidebar + top bar
- [ ] Mock data layer
- [ ] Metric cards (top row)
- [ ] Area status table
- [ ] Wait time line chart
- [ ] Alerts panel
- [ ] WebSocket client and hook
- [ ] Wire live data to all components

---

## Visual reference

Tema claro. Left sidebar (240px fixed). Top bar (64px).
Top row: 4 metric cards with large numbers.
Center: real-time line chart (left) + area status table (right).
Bottom: active patients table.
Right column: alerts panel.

**Color palette — use these exactly:**
```
Background:       #F4F6FA   (gris-azul muy suave)
Card background:  #FFFFFF
Card border:      #DDE1EC
Sidebar bg:       #FFFFFF   (con sombra leve, no borde)
Green accent:     #008A4B   (verde Salud Digna)
Blue accent:      #005B9F   (azul médico)
Text primary:     #1A1D2E   (navy oscuro)
Text secondary:   #6B7080   (gris medio)
Alert red:        #DC2626
Alert yellow:     #D97706
```

---

## Task 1 — Project initialization

```bash
cd apps/dashboard
npx create-next-app@14 . --typescript --tailwind --eslint --app --no-src-dir
pnpm add recharts lucide-react
pnpm add -D @types/node
```

Agregar en `app/globals.css` con `@theme` (Tailwind v4):
```css
@theme {
  --color-brand-green:        #008A4B;
  --color-brand-blue:         #005B9F;
  --color-surface-base:       #F4F6FA;
  --color-surface-card:       #FFFFFF;
  --color-surface-border:     #DDE1EC;
  --color-content-primary:    #1A1D2E;
  --color-content-secondary:  #6B7080;
  --color-alert-red:          #DC2626;
  --color-alert-yellow:       #D97706;
}

body {
  background-color: #F4F6FA;
  color: #1A1D2E;
}
```

**Acceptance criteria:**
- `pnpm dev` starts at `http://localhost:3000` without errors
- Custom Tailwind colors work in components
- TypeScript strict mode enabled

---

## Task 2 — Layout: sidebar + top bar

Create the persistent shell in `app/layout.tsx`.

**File structure:**
```
app/
├── layout.tsx
├── page.tsx               ← redirects to /dashboard
└── dashboard/
    └── page.tsx
components/
├── layout/
│   ├── Sidebar.tsx
│   └── TopBar.tsx
├── ui/
│   ├── MetricCard.tsx
│   ├── AreaTable.tsx
│   ├── WaitTimeChart.tsx
│   └── AlertsPanel.tsx
lib/
├── mock-data.ts
├── api-client.ts
├── websocket-client.ts
└── hooks/
    └── useDashboardData.ts
```

**Sidebar (left, fixed, 240px):**
- Top: "SaludCopilot" in green bold, subtitle "Salud Digna"
- Navigation links with lucide-react icons:
  - Dashboard (`LayoutDashboard` icon) — active = green left border + green text
  - Áreas (`MapPin` icon)
  - Alertas (`Bell` icon) — shows red badge with count if alerts > 0
  - Historial (`Clock` icon)
- Bottom: clinic name + green pulsing dot when WebSocket connected

**Top bar (64px, right of sidebar):**
- Left: page title
- Right: clock updating every second + "EN VIVO" badge (green, pulsing dot)
  — badge only shows when WebSocket is connected

**Acceptance criteria:**
- Sidebar renders all 4 nav items with icons
- Active route highlighted with green left border
- Layout renders at 1280px minimum width without overflow

---

## Task 3 — Mock data layer

Create `lib/mock-data.ts`.

```typescript
export const mockSummary = {
  total_active_visits: 23,
  total_waiting_patients: 18,
  average_wait_minutes: 14,
  areas_at_risk: 2,
}

export const mockAreas = [
  {
    area_id: "area-001",
    area_name: "Laboratorio",
    current_queue_length: 8,
    estimated_wait_minutes: 22,
    people_in_area: 6,      // from CV worker
    status: "saturated",   // "normal" | "warning" | "saturated"
  },
  {
    area_id: "area-002",
    area_name: "Ultrasonido",
    current_queue_length: 3,
    estimated_wait_minutes: 12,
    people_in_area: 2,
    status: "normal",
  },
  {
    area_id: "area-003",
    area_name: "Rayos X",
    current_queue_length: 5,
    estimated_wait_minutes: 18,
    people_in_area: 4,
    status: "warning",
  },
  {
    area_id: "area-004",
    area_name: "Electrocardiograma",
    current_queue_length: 1,
    estimated_wait_minutes: 5,
    people_in_area: 1,
    status: "normal",
  },
]

export const mockActiveVisits = [
  { visit_id: "v-001", patient_name: "María García",
    current_area: "Laboratorio", step_order: 1, total_steps: 2,
    status: "in_progress", waiting_since_minutes: 8 },
  { visit_id: "v-002", patient_name: "Carlos López",
    current_area: "Ultrasonido", step_order: 2, total_steps: 2,
    status: "in_progress", waiting_since_minutes: 3 },
  { visit_id: "v-003", patient_name: "Ana Martínez",
    current_area: "Rayos X", step_order: 1, total_steps: 1,
    status: "in_progress", waiting_since_minutes: 12 },
  { visit_id: "v-004", patient_name: "Luis Hernández",
    current_area: "Laboratorio", step_order: 1, total_steps: 3,
    status: "in_progress", waiting_since_minutes: 5 },
  { visit_id: "v-005", patient_name: "Rosa Sánchez",
    current_area: "Electrocardiograma", step_order: 1, total_steps: 1,
    status: "in_progress", waiting_since_minutes: 2 },
]

// 12 data points = last 60 minutes (one per 5 min)
export const mockWaitTimeHistory = {
  labels: ["55m", "50m", "45m", "40m", "35m", "30m",
           "25m", "20m", "15m", "10m", "5m", "ahora"],
  series: {
    "Laboratorio":       [18, 20, 22, 25, 24, 22, 20, 22, 24, 26, 24, 22],
    "Ultrasonido":       [10, 12, 11, 13, 14, 12, 11, 12, 13, 12, 11, 12],
    "Rayos X":           [15, 16, 18, 17, 16, 18, 19, 18, 17, 18, 18, 18],
    "Electrocardiograma":[4,  5,  4,  5,  5,  4,  5,  5,  4,  5,  5,  5],
  },
}

export const mockAlerts = [
  { id: "a-001", severity: "critical", area_name: "Laboratorio",
    message: "Cola de 8 pacientes. Capacidad máxima alcanzada.",
    triggered_at: new Date(Date.now() - 5 * 60000).toISOString() },
  { id: "a-002", severity: "warning", area_name: "Rayos X",
    message: "Espera estimada supera 15 minutos.",
    triggered_at: new Date(Date.now() - 12 * 60000).toISOString() },
  { id: "a-003", severity: "info", area_name: "Ultrasonido",
    message: "Paciente urgente en cola.",
    triggered_at: new Date(Date.now() - 2 * 60000).toISOString() },
]
```

**Acceptance criteria:**
- Structure matches exactly what the API will return
- All components build and render using this mock without errors

---

## Task 4 — Metric cards

Create `components/ui/MetricCard.tsx`.

**Four cards across the top:**

| Label | Value source | Accent |
|---|---|---|
| Pacientes activos | `total_active_visits` | green |
| En espera | `total_waiting_patients` | blue |
| Espera promedio | `average_wait_minutes` + " min" | neutral |
| Áreas en riesgo | `areas_at_risk` | red if > 0, green if 0 |

**Design per card:**
- Background: `surface-card`, border: `surface-border`
- Thin top border in accent color (4px)
- Label: small, `content-secondary`
- Value: 48px bold, accent color
- Optional unit below value: small, `content-secondary`
- Bottom right: trend arrow + percentage (use a `trend?: number` prop)

```typescript
interface MetricCardProps {
  label: string
  value: number | string
  unit?: string
  accentColor: string     // hex color
  trend?: number          // +12.5 means up 12.5%, negative means down
}
```

**Acceptance criteria:**
- 4-column grid, responsive to 2-column on smaller screens
- Trend shows green ↑ for positive, red ↓ for negative
- Renders with mock data without TypeScript errors

---

## Task 5 — Area status table

Create `components/ui/AreaTable.tsx`.

**Columns:**
| Área | Pacientes en cola | 📷 Personas físicas | Espera est. | Estado |
|---|---|---|---|---|

**Status badge:**
- `normal` → green pill: "Normal"
- `warning` → yellow pill: "Alerta"
- `saturated` → red pill: "Saturado" + entire row has `bg-red-950/30`

**"Personas físicas" column** has a camera icon (`Camera` from lucide-react)
before the number — visual cue that this data comes from the CV worker.

**Acceptance criteria:**
- All areas render from mock data
- Saturated rows have red background tint
- Status badges use correct colors
- Camera icon visible in the physical count column header

---

## Task 6 — Wait time line chart

Create `components/ui/WaitTimeChart.tsx`.

**Line chart: wait time per area over last 60 minutes.**
Uses Recharts `LineChart`.

```typescript
// Line colors per area — consistent across all components
const AREA_COLORS: Record<string, string> = {
  "Laboratorio":        "#008A4B",
  "Ultrasonido":        "#005B9F",
  "Rayos X":            "#F6AD55",
  "Electrocardiograma": "#9F7AEA",
}
```

**Chart spec:**
- X axis: time labels from `mockWaitTimeHistory.labels`
- Y axis: minutes (0 to max + 5 buffer)
- Grid: subtle `#2A2D3A` lines
- Tooltip: dark background, shows area + exact minutes
- Legend: at bottom, colored dots
- Lines: smooth (`type="monotone"`), strokeWidth 2, no dots

**Live behavior (after WebSocket):**
When `wait_time_updated` event arrives, append new point and
drop oldest — keeps exactly 12 points.

**Acceptance criteria:**
- Chart renders with mock history data
- Correct color per area matches `AREA_COLORS`
- Tooltip shows area name and minutes on hover
- `ResponsiveContainer` fills parent width

---

## Task 7 — Alerts panel

Create `components/ui/AlertsPanel.tsx`.

```typescript
interface Alert {
  id: string
  severity: "critical" | "warning" | "info"
  area_name: string
  message: string
  triggered_at: string  // ISO8601
}
```

**Design:**
- Each alert: card with colored left border (red/yellow/blue per severity)
- Top: area name (bold) + severity icon
- Middle: message text
- Bottom: "hace N minutos" (relative time, updates live)
- Newest alert at top
- "Limpiar resueltas" button: removes all non-critical alerts

**Empty state:**
When no alerts: centered checkmark icon (`CheckCircle2`) + "Sin alertas activas" in green.

**Acceptance criteria:**
- All 3 severity types render with correct border colors
- Relative timestamps update every minute
- Empty state shows when alerts array is empty
- "Limpiar resueltas" removes warning + info alerts, keeps critical

---

## Task 8 — WebSocket client and data hook

Create `lib/websocket-client.ts`:

```typescript
export class DashboardWebSocketClient {
  connect(clinicId: string, onEvent: (e: DashboardEvent) => void): void
  // URL: ws://localhost:8000/ws/dashboard/{clinicId}
  // On close: reconnect after 3 seconds
  // On error: log and reconnect

  disconnect(): void
  get isConnected(): boolean
}
```

Create `lib/hooks/useDashboardData.ts`:

```typescript
export function useDashboardData(clinicId: string) {
  // Initialize state with mock data
  // Connect WebSocket on mount, disconnect on unmount
  // Handle events:
  //   wait_time_updated → update area estimate + append to chart history
  //   queue_changed     → update area queue length
  //   visit_updated     → update active visits table
  //   alert             → prepend to alerts array

  return { areas, activeVisits, summary, alerts, isConnected }
}
```

**Fallback behavior:**
If WebSocket fails to connect after 5 seconds, stay on mock data.
Show "DEMO" badge instead of "EN VIVO" in top bar.

**Acceptance criteria:**
- `isConnected` drives "EN VIVO" vs "DEMO" badge
- Each event type updates the correct state slice
- No stale closures — state updates trigger re-renders
- Reconnects automatically on disconnect

---

## Task 9 — Wire everything in dashboard page

Update `app/dashboard/page.tsx`:

```typescript
export default function DashboardPage() {
  const { areas, activeVisits, summary, alerts, isConnected } =
    useDashboardData(process.env.NEXT_PUBLIC_CLINIC_ID ?? "default")

  return (
    <div className="space-y-6">
      {/* Row 1: 4 metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Pacientes activos" value={summary.total_active_visits} accentColor="#008A4B" />
        <MetricCard label="En espera" value={summary.total_waiting_patients} accentColor="#005B9F" />
        <MetricCard label="Espera promedio" value={summary.average_wait_minutes} unit="min" accentColor="#F0F0F0" />
        <MetricCard label="Áreas en riesgo" value={summary.areas_at_risk}
          accentColor={summary.areas_at_risk > 0 ? "#E53E3E" : "#008A4B"} />
      </div>

      {/* Row 2: chart + area table */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <WaitTimeChart history={waitTimeHistory} />
        </div>
        <AlertsPanel alerts={alerts} />
      </div>

      {/* Row 3: area table full width */}
      <AreaTable areas={areas} />

      {/* Row 4: active visits */}
      {/* Simple table: name, current area, step progress, waiting time */}
    </div>
  )
}
```

Add `NEXT_PUBLIC_CLINIC_ID` to `.env.example`.

**Acceptance criteria:**
- Page loads with mock data immediately (no loading state flash)
- Live data replaces mock seamlessly when WebSocket connects
- No layout shifts on data updates
- All four sections visible without scrolling at 1280px

---

## Do not implement yet

- Login / authentication page
- Historical reports with date filtering
- Multi-clinic view
- Export to PDF or CSV
- Mobile responsive layout
- Map/croquis upload per area (Fase 2: manager uploads floor plan image,
  system sends it via WhatsApp instead of text navigation instructions)
- Navigation instructions editor in dashboard UI (Fase 2: visual form
  for managers to set navigation_instructions per area)