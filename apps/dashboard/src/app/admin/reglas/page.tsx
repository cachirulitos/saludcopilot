"use client";

import { useState, useEffect } from "react";
import { Loader2, AlertCircle, ScrollText } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Rule {
  id: string;
  code: string;
  description: string;
  rule_type: string;
  active: boolean;
  condition: Record<string, unknown> | null;
  effect: Record<string, unknown> | null;
}

const TYPE_COLORS: Record<string, string> = {
  order:       "bg-blue-100 text-blue-700 border-blue-300",
  priority:    "bg-yellow-100 text-yellow-700 border-yellow-300",
  restriction: "bg-red-100 text-red-700 border-red-300",
};

export default function ReglasPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/admin/rules`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setRules)
      .catch(() => setError("No se pudo conectar con la API."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-content-primary)]">
          Reglas clínicas
        </h1>
        <p className="text-sm text-[var(--color-content-secondary)] mt-0.5">
          Reglas del motor de secuenciación de visitas
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-[var(--color-content-secondary)] py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Cargando reglas...</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0" />
          {error}
        </div>
      )}

      {!loading && !error && rules.length === 0 && (
        <div className="bg-[var(--color-surface-card)] border border-[var(--color-surface-border)] rounded-lg py-16 flex flex-col items-center gap-3">
          <ScrollText className="w-10 h-10 text-[var(--color-surface-border)]" />
          <p className="text-[var(--color-content-secondary)] text-sm">
            No hay reglas registradas. Ejecuta el seed script para cargar las reglas base.
          </p>
        </div>
      )}

      {!loading && !error && rules.length > 0 && (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="bg-[var(--color-surface-card)] border border-[var(--color-surface-border)] rounded-lg p-5"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-mono text-sm font-semibold text-[var(--color-content-primary)]">
                      {rule.code}
                    </span>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${
                        TYPE_COLORS[rule.rule_type] ?? "bg-gray-100 text-gray-500 border-gray-200"
                      }`}
                    >
                      {rule.rule_type}
                    </span>
                    {!rule.active && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-400 border border-gray-200">
                        inactiva
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--color-content-secondary)]">{rule.description}</p>
                </div>
              </div>

              {(rule.condition || rule.effect) && (
                <div className="grid grid-cols-2 gap-3 mt-4">
                  {rule.condition && (
                    <div>
                      <p className="text-xs font-medium text-[var(--color-content-secondary)] mb-1">
                        Condición
                      </p>
                      <pre className="text-xs bg-[var(--color-surface-base)] border border-[var(--color-surface-border)] rounded p-2 overflow-x-auto text-[var(--color-content-secondary)]">
                        {JSON.stringify(rule.condition, null, 2)}
                      </pre>
                    </div>
                  )}
                  {rule.effect && (
                    <div>
                      <p className="text-xs font-medium text-[var(--color-content-secondary)] mb-1">
                        Efecto
                      </p>
                      <pre className="text-xs bg-[var(--color-surface-base)] border border-[var(--color-surface-border)] rounded p-2 overflow-x-auto text-[var(--color-content-secondary)]">
                        {JSON.stringify(rule.effect, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
