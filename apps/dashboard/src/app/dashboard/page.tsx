"use client";
import { useDashboardData } from "@/lib/hooks/useDashboardData";
import { MetricCard } from "@/components/ui/MetricCard";
import { AreaTable } from "@/components/ui/AreaTable";
import WaitTimeChart from "@/components/ui/WaitTimeChart";
import AlertsPanel from "@/components/ui/AlertsPanel";
import { Alert } from "@/components/ui/AlertsPanel";

export default function DashboardPage() {
  const {
    areas,
    activeVisits,
    summary,
    alerts,
    isConnected,
    waitTimeHistory,
    clearResolvedAlerts,
  } = useDashboardData(process.env.NEXT_PUBLIC_CLINIC_ID ?? "default");

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Pacientes activos"
          value={summary.total_active_visits}
          accentColor="#008A4B"
        />
        <MetricCard
          label="En espera"
          value={summary.total_waiting_patients}
          accentColor="#005B9F"
        />
        <MetricCard
          label="Espera promedio"
          value={summary.average_wait_minutes}
          unit="min"
          accentColor="#37415180"
        />
        <MetricCard
          label="Áreas en riesgo"
          value={summary.areas_at_risk}
          accentColor={summary.areas_at_risk > 0 ? "#E53E3E" : "#008A4B"}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-[var(--color-surface-card)] rounded-lg p-4 border border-[var(--color-surface-border)] shadow-sm">
          <h2 className="text-[var(--color-content-secondary)] text-sm mb-4 font-medium">
            Tiempos de espera — Últimos 60 min
          </h2>
          <WaitTimeChart history={waitTimeHistory} />
        </div>
        <AlertsPanel
          alerts={alerts as Alert[]}
          onClearResolved={clearResolvedAlerts}
        />
      </div>

      <AreaTable areas={areas} />

      {/* Active visits fallback for UI completion per Task 9 instructions, although not explicitly mapped in UI components yet */}
      <div className="bg-[var(--color-surface-card)] rounded-lg p-6 border border-[var(--color-surface-border)] shadow-sm">
        <h2 className="text-[var(--color-content-primary)] font-semibold mb-4">
          Pacientes Activos Recientes
        </h2>
        <div className="text-sm text-[var(--color-content-secondary)]">
          {activeVisits.slice(0, 3).map((v) => (
            <div
              key={v.visit_id}
              className="py-2 border-b last:border-0 border-[var(--color-surface-border)] flex justify-between">
              <span>
                <strong className="text-[var(--color-content-primary)]">
                  {v.patient_name}
                </strong>{" "}
                — {v.current_area}
              </span>
              <span>
                Paso {v.step_order} de {v.total_steps} (
                {v.waiting_since_minutes} min espera)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
