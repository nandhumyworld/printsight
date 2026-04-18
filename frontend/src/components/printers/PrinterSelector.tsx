import { usePrinter } from '@/context/PrinterContext';
import { ChevronDown, Printer } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';

export function PrinterSelector() {
  const { printers, selectedPrinter, setSelectedPrinter, isLoading } = usePrinter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (isLoading) return <div className="h-8 w-40 animate-pulse rounded-md bg-muted" />;
  if (!printers.length) return null;

  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted/50 transition-colors"
      >
        {selectedPrinter?.image_url ? (
          <img
            src={`${API_BASE}${selectedPrinter.image_url}`}
            alt=""
            className="h-5 w-5 rounded object-cover"
          />
        ) : (
          <Printer className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="max-w-[140px] truncate font-medium">
          {selectedPrinter?.name ?? 'Select printer'}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[200px] rounded-md border bg-card shadow-md">
          {printers.map((p) => (
            <button
              key={p.id}
              onClick={() => { setSelectedPrinter(p); setOpen(false); }}
              className={`flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 transition-colors ${p.id === selectedPrinter?.id ? 'bg-primary/5 font-medium' : ''}`}
            >
              {p.image_url ? (
                <img src={`${API_BASE}${p.image_url}`} alt="" className="h-5 w-5 rounded object-cover" />
              ) : (
                <Printer className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="truncate">{p.name}</span>
              {!p.is_active && (
                <span className="ml-auto text-xs text-muted-foreground">archived</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
