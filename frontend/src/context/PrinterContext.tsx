import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '@/services/api';
import type { ApiResponse, Printer } from '@/types';

const STORAGE_KEY = 'printsight_selected_printer_id';

interface PrinterContextValue {
  printers: Printer[];
  selectedPrinter: Printer | null;
  setSelectedPrinter: (printer: Printer) => void;
  isLoading: boolean;
  refetchPrinters: () => Promise<void>;
}

const PrinterContext = createContext<PrinterContextValue | null>(null);

export function PrinterProvider({ children }: { children: React.ReactNode }) {
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [selectedPrinter, setSelectedPrinterState] = useState<Printer | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadPrinters = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data: response } = await api.get<ApiResponse<Printer[]>>('/printers');
      const list: Printer[] = response.data;
      setPrinters(list);

      const storedId = localStorage.getItem(STORAGE_KEY);
      const storedPrinter = storedId
        ? list.find((p) => p.id === Number(storedId)) ?? null
        : null;

      setSelectedPrinterState(storedPrinter ?? list[0] ?? null);
    } catch {
      setPrinters([]);
      setSelectedPrinterState(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrinters();
  }, [loadPrinters]);

  const setSelectedPrinter = useCallback((printer: Printer) => {
    setSelectedPrinterState(printer);
    localStorage.setItem(STORAGE_KEY, String(printer.id));
  }, []);

  const refetchPrinters = useCallback(async () => {
    await loadPrinters();
  }, [loadPrinters]);

  const value = useMemo(
    () => ({ printers, selectedPrinter, setSelectedPrinter, isLoading, refetchPrinters }),
    [printers, selectedPrinter, setSelectedPrinter, isLoading, refetchPrinters]
  );

  return <PrinterContext.Provider value={value}>{children}</PrinterContext.Provider>;
}

export function usePrinter(): PrinterContextValue {
  const ctx = useContext(PrinterContext);
  if (!ctx) throw new Error('usePrinter must be used within PrinterProvider');
  return ctx;
}
