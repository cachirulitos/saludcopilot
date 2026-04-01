import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { DashboardWebSocketClient, DashboardEvent } from '../websocket-client';
import {
  mockAreas,
  mockActiveVisits,
  mockAlerts,
  mockWaitTimeHistory,
} from '../mock-data';

const CHART_WINDOW = 12;

export function useDashboardData(
  clinicId: string,
  onConnectionChange?: (connected: boolean) => void,
  onAlertCountChange?: (count: number) => void,
) {
  const [areas, setAreas] = useState(mockAreas);
  const [activeVisits, setActiveVisits] = useState(mockActiveVisits);
  const [alerts, setAlerts] = useState(mockAlerts);
  const [waitTimeHistory, setWaitTimeHistory] = useState(mockWaitTimeHistory);
  const [isConnected, setIsConnected] = useState(false);

  const wsClientRef = useRef<DashboardWebSocketClient | null>(null);

  // Derived summary — recomputed whenever areas change
  const summary = useMemo(() => {
    const totalWaiting = areas.reduce((s, a) => s + a.current_queue_length, 0);
    const totalPeople = areas.reduce((s, a) => s + a.people_in_area, 0);
    const areasAtRisk = areas.filter(
      (a) => a.status === 'warning' || a.status === 'saturated',
    ).length;
    const avgWait =
      areas.length > 0
        ? Math.round(
            areas.reduce((s, a) => s + a.estimated_wait_minutes, 0) /
              areas.length,
          )
        : 0;
    return {
      total_active_visits: totalPeople,
      total_waiting_patients: totalWaiting,
      average_wait_minutes: avgWait,
      areas_at_risk: areasAtRisk,
    };
  }, [areas]);

  // Propagate alert count upward whenever alerts list changes
  useEffect(() => {
    onAlertCountChange?.(alerts.filter((a) => a.severity === 'critical').length);
  }, [alerts, onAlertCountChange]);

  const handleWebSocketEvent = useCallback((event: DashboardEvent) => {
    switch (event.event) {
      case 'wait_time_updated':
        setAreas((prev) => {
          const updated = prev.map((area) =>
            area.area_id === event.area_id
              ? {
                  ...area,
                  estimated_wait_minutes: event.data.estimated_minutes,
                  people_in_area: event.data.people_count,
                }
              : area,
          );

          // Slide chart window: shift left + append latest value at "ahora"
          const targetArea = updated.find((a) => a.area_id === event.area_id);
          if (targetArea) {
            setWaitTimeHistory((hist) => {
              const existingSeries = hist.series[targetArea.area_name] ?? Array(CHART_WINDOW).fill(0);
              const newSeries = [...existingSeries.slice(1), event.data.estimated_minutes];
              const nowLabel = new Date().toLocaleTimeString('es-MX', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
              });
              const newLabels = [...hist.labels.slice(1), nowLabel];
              return {
                labels: newLabels,
                series: { ...hist.series, [targetArea.area_name]: newSeries },
              };
            });
          }

          return updated;
        });
        break;

      case 'queue_changed':
        setAreas((prev) =>
          prev.map((area) =>
            area.area_id === event.area_id
              ? {
                  ...area,
                  current_queue_length: event.data.current_queue_length,
                  status: event.data.status ?? area.status,
                }
              : area,
          ),
        );
        break;

      case 'alert': {
        const newAlert = event.data;
        setAlerts((prev) => [newAlert, ...prev].slice(0, 50));
        break;
      }
    }
  }, []);

  const handleConnectionStatus = useCallback(
    (status: boolean) => {
      setIsConnected(status);
      onConnectionChange?.(status);
    },
    [onConnectionChange],
  );

  useEffect(() => {
    if (!clinicId) return;

    const client = new DashboardWebSocketClient();
    wsClientRef.current = client;
    client.connect(clinicId, handleWebSocketEvent, handleConnectionStatus);

    // Re-render alerts every minute to refresh relative timestamps
    const timer = setInterval(() => setAlerts((prev) => [...prev]), 60_000);

    return () => {
      client.disconnect();
      clearInterval(timer);
    };
  }, [clinicId, handleWebSocketEvent, handleConnectionStatus]);

  return {
    areas,
    activeVisits,
    summary,
    alerts,
    isConnected,
    waitTimeHistory,
    clearResolvedAlerts: () =>
      setAlerts((prev) => prev.filter((a) => a.severity === 'critical')),
  };
}
