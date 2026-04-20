import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Download, Upload, X, Check } from 'lucide-react';

interface DiffEntry { old: string | null; new: string | null }

interface Props {
  printerId: string;
  onApplied: () => void;
}

export function ColumnMappingExportImport({ printerId, onApplied }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [diff, setDiff] = useState<Record<string, DiffEntry> | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleExport = async () => {
    try {
      const { data } = await api.get(`/printers/${printerId}/mapping/export`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `mapping_printer_${printerId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently ignore — user will see nothing downloaded
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setError('');
    setLoading(true);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/printers/${printerId}/mapping/import/preview`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDiff(data.data.diff);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Preview failed');
      setPendingFile(null);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleApply = async () => {
    if (!pendingFile) return;
    setLoading(true);
    const form = new FormData();
    form.append('file', pendingFile);
    try {
      await api.post(`/printers/${printerId}/mapping/import/apply`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDiff(null);
      setPendingFile(null);
      onApplied();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Apply failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={handleExport}>
        <Download className="mr-1.5 h-3.5 w-3.5" /> Export JSON
      </Button>
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={loading}>
        <Upload className="mr-1.5 h-3.5 w-3.5" /> Import JSON
      </Button>
      <input ref={fileRef} type="file" accept=".json" className="hidden" onChange={handleFileSelect} />

      {diff !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl mx-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Mapping Diff</h3>
              <button onClick={() => { setDiff(null); setPendingFile(null); }} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            {Object.keys(diff).length === 0 ? (
              <p className="text-sm text-muted-foreground">No changes — imported mapping is identical to current.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-1">
                {Object.entries(diff).map(([field, { old: o, new: n }]) => (
                  <div key={field} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="font-mono font-medium w-36 truncate">{field}</span>
                    <span className="text-destructive line-through text-xs">{o ?? '(none)'}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="text-emerald-600 text-xs">{n ?? '(removed)'}</span>
                  </div>
                ))}
              </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-3">
              <Button variant="outline" size="sm" onClick={() => { setDiff(null); setPendingFile(null); }}>Cancel</Button>
              <Button size="sm" onClick={handleApply} disabled={loading || Object.keys(diff).length === 0} isLoading={loading}>
                <Check className="mr-1.5 h-3.5 w-3.5" /> Apply
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
