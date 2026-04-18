import { useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertTriangle, X } from 'lucide-react';

type DeleteMode = 'archive' | 'hard' | 'purge';

interface Props {
  printer: { id: number; name: string };
  onClose: () => void;
  onDeleted: () => void;
}

export function DeletePrinterDialog({ printer, onClose, onDeleted }: Props) {
  const [mode, setMode] = useState<DeleteMode>('archive');
  const [confirmName, setConfirmName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAction = async () => {
    setError('');
    setLoading(true);
    try {
      if (mode === 'archive') {
        await api.post(`/printers/${printer.id}/archive`);
        onDeleted();
      } else if (mode === 'hard') {
        await api.delete(`/printers/${printer.id}`);
        onDeleted();
      } else {
        await api.post(`/printers/${printer.id}/purge`, { confirm_name: confirmName });
        onDeleted();
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Action failed');
    } finally {
      setLoading(false);
    }
  };

  const canSubmit =
    mode === 'archive' ||
    mode === 'hard' ||
    (mode === 'purge' && confirmName === printer.name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-xl border bg-card p-6 shadow-xl mx-4">
        <button onClick={onClose} className="absolute right-4 top-4 text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-full bg-destructive/10 p-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
          </div>
          <div>
            <h2 className="font-semibold">Remove Printer</h2>
            <p className="text-sm text-muted-foreground">{printer.name}</p>
          </div>
        </div>

        <div className="space-y-2 mb-4">
          {[
            { value: 'archive' as DeleteMode, label: 'Archive', desc: 'Hide from active views. Can be restored later.' },
            { value: 'hard' as DeleteMode, label: 'Delete', desc: 'Permanently delete. Only works if no uploads exist.' },
            { value: 'purge' as DeleteMode, label: 'Purge (all data)', desc: 'Cascade-delete printer + all jobs, uploads, costs.' },
          ].map((opt) => (
            <label key={opt.value} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${mode === opt.value ? 'border-destructive bg-destructive/5' : 'hover:bg-muted/30'}`}>
              <input
                type="radio"
                name="deleteMode"
                value={opt.value}
                checked={mode === opt.value}
                onChange={() => setMode(opt.value)}
                className="mt-0.5"
              />
              <div>
                <p className="font-medium text-sm">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>

        {mode === 'purge' && (
          <div className="mb-4 space-y-1">
            <Label>Type <strong>{printer.name}</strong> to confirm</Label>
            <Input
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
              placeholder={printer.name}
            />
          </div>
        )}

        {error && <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

        <div className="flex gap-3">
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button variant="destructive" onClick={handleAction} disabled={!canSubmit || loading} isLoading={loading}>
            {mode === 'archive' ? 'Archive' : mode === 'hard' ? 'Delete' : 'Purge'}
          </Button>
        </div>
      </div>
    </div>
  );
}
