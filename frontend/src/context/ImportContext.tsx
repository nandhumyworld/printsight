import React, { createContext, useCallback, useContext, useRef, useState } from 'react';

export interface ImportResult {
  batch_id: number;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  skipped_details: { row_number: number; reason: string }[];
  message: string;
}

export interface ImportState {
  status: 'idle' | 'running' | 'done' | 'error';
  progress: { done: number; total: number };
  result: ImportResult | null;
  filename: string;
}

const DEFAULT_STATE: ImportState = {
  status: 'idle',
  progress: { done: 0, total: 0 },
  result: null,
  filename: '',
};

interface ImportContextValue {
  getState: (printerId: string) => ImportState;
  startImport: (printerId: string, file: File) => void;
  clearState: (printerId: string) => void;
}

const ImportContext = createContext<ImportContextValue | null>(null);

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

export function ImportProvider({ children }: { children: React.ReactNode }) {
  const [states, setStates] = useState<Record<string, ImportState>>({});
  // Keep a ref so the fetch closure always reads latest states without re-creating
  const statesRef = useRef(states);
  statesRef.current = states;

  const setState = useCallback((printerId: string, patch: Partial<ImportState>) => {
    setStates(prev => ({
      ...prev,
      [printerId]: { ...(prev[printerId] ?? DEFAULT_STATE), ...patch },
    }));
  }, []);

  const getState = useCallback((printerId: string): ImportState => {
    return states[printerId] ?? DEFAULT_STATE;
  }, [states]);

  const clearState = useCallback((printerId: string) => {
    setStates(prev => {
      const next = { ...prev };
      delete next[printerId];
      return next;
    });
  }, []);

  const startImport = useCallback((printerId: string, file: File) => {
    console.log('[Import] startImport called', printerId, file.name);
    setState(printerId, {
      status: 'running',
      progress: { done: 0, total: 0 },
      result: null,
      filename: file.name,
    });
    console.log('[Import] state set to running');

    const token = localStorage.getItem('access_token');
    const formData = new FormData();
    formData.append('file', file);

    (async () => {
      try {
        console.log('[Import] fetch starting', `${API_URL}/api/v1/printers/${printerId}/uploads`);
        const resp = await fetch(`${API_URL}/api/v1/printers/${printerId}/uploads`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        console.log('[Import] fetch response', resp.status, resp.ok, 'has body:', !!resp.body);

        if (!resp.ok || !resp.body) {
          console.error('[Import] fetch failed or no body');
          setState(printerId, { status: 'error' });
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        let evtCount = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) { console.log('[Import] stream done, events received:', evtCount); break; }
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const evt = JSON.parse(line.slice(6));
              evtCount++;
              if (evtCount <= 3 || evt.complete) console.log('[Import] event', evt);
              setState(printerId, { progress: { done: evt.done, total: evt.total } });
              if (evt.complete) {
                setState(printerId, {
                  status: 'done',
                  result: {
                    batch_id: evt.batch_id,
                    rows_total: evt.rows_total,
                    rows_imported: evt.rows_imported,
                    rows_skipped: evt.rows_skipped,
                    skipped_details: evt.skipped_details ?? [],
                    message: evt.message,
                  },
                });
              }
            } catch {
              // ignore malformed event
            }
          }
        }
      } catch (err) {
        console.error('[Import] fetch threw', err);
        setState(printerId, { status: 'error' });
      }
    })();
  }, [setState]);

  return (
    <ImportContext.Provider value={{ getState, startImport, clearState }}>
      {children}
    </ImportContext.Provider>
  );
}

export function useImport(printerId: string): ImportState & {
  startImport: (file: File) => void;
  clearState: () => void;
} {
  const ctx = useContext(ImportContext);
  if (!ctx) throw new Error('useImport must be used within ImportProvider');
  const state = ctx.getState(printerId);
  console.log('[Import] useImport render', printerId, state.status);
  return {
    ...state,
    startImport: (file: File) => ctx.startImport(printerId, file),
    clearState: () => ctx.clearState(printerId),
  };
}
