import { useState, useEffect, useCallback, useRef } from 'react';
import { DashboardWebSocketClient, DashboardEvent } from '../websocket-client';
import { 
  mockAreas, 
  mockActiveVisits, 
  mockSummary, 
  mockAlerts, 
  mockWaitTimeHistory 
} from '../mock-data';

export function useDashboardData(clinicId: string) {
  const [areas, setAreas] = useState(mockAreas);
  const [activeVisits, setActiveVisits] = useState(mockActiveVisits);
  const [summary, setSummary] = useState(mockSummary);
  const [alerts, setAlerts] = useState(mockAlerts);
  const [waitTimeHistory, setWaitTimeHistory] = useState(mockWaitTimeHistory);
  const [isConnected, setIsConnected] = useState(false);
  
  const wsClientRef = useRef<DashboardWebSocketClient | null>(null);

  const handleWebSocketEvent = useCallback((event: DashboardEvent) => {
    switch (event.event) {
      case 'wait_time_updated':
        // data: { estimated_minutes: N, people_count: N }
        setAreas(prev => prev.map(area => 
          area.area_id === event.area_id 
            ? { ...area, 
                estimated_wait_minutes: event.data.estimated_minutes,
                people_in_area: event.data.people_count
              }
            : area
        ));
        // Note: Realistically we'd also update the chart here, but for now 
        // we'll keep the mock chart data static unless we receive a specific historical update event
        break;
        
      case 'queue_changed':
        // data: { current_queue_length: N, status: 'normal'|'warning'|'saturated' }
        setAreas(prev => prev.map(area => 
          area.area_id === event.area_id 
            ? { ...area, 
                current_queue_length: event.data.current_queue_length,
                status: event.data.status || area.status
              }
            : area
        ));
        break;
        
      case 'visit_updated':
        // Re-fetch visits from API or handle granular update
        // We'll just patch the specific visit if we have it conceptually
        break;
        
      case 'alert':
        const newAlert = event.data;
        setAlerts(prev => [newAlert, ...prev].slice(0, 50)); // Keep max 50
        break;
    }
  }, []);

  const handleConnectionStatus = useCallback((status: boolean) => {
    setIsConnected(status);
  }, []);

  useEffect(() => {
    if (!clinicId) return;

    const client = new DashboardWebSocketClient();
    wsClientRef.current = client;

    client.connect(clinicId, handleWebSocketEvent, handleConnectionStatus);

    // Fallback: update alerts relative time every minute to trigger re-renders
    const timer = setInterval(() => {
      setAlerts(prev => [...prev]);
    }, 60000);

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
    // Provide a helper to clear alerts to UI
    clearResolvedAlerts: () => setAlerts(prev => prev.filter(a => a.severity === 'critical'))
  };
}
