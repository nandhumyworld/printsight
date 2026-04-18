import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft } from 'lucide-react';
import { PrinterImageDropzone } from '@/components/printers/PrinterImageDropzone';
import { DeletePrinterDialog } from '@/components/printers/DeletePrinterDialog';
import { usePrinter } from '@/context/PrinterContext';

export default function EditPrinterPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { refetchPrinters } = usePrinter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [showDelete, setShowDelete] = useState(false);
  const [localImageUrl, setLocalImageUrl] = useState<string | null | undefined>(undefined);

  const { data: printer, isLoading } = useQuery({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then(r => r.data.data),
  });

  const [form, setForm] = useState<{ name: string; model: string; type: string; serial_number: string; location: string } | null>(null);

  if (!form && printer) {
    setForm({
      name: printer.name ?? '',
      model: printer.model ?? '',
      type: printer.type ?? '',
      serial_number: printer.serial_number ?? '',
      location: printer.location ?? '',
    });
  }

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => f ? { ...f, [field]: e.target.value } : f);

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    setError('');
    try {
      await api.put(`/printers/${id}`, form);
      qc.invalidateQueries({ queryKey: ['printer', id] });
      await refetchPrinters();
      navigate(`/printers/${id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpdate = (imageUrl: string | null) => {
    setLocalImageUrl(imageUrl);
    qc.invalidateQueries({ queryKey: ['printer', id] });
    refetchPrinters();
  };

  if (isLoading || !form) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  if (!printer) return <div className="text-center py-20 text-muted-foreground">Printer not found</div>;

  const currentImageUrl = localImageUrl !== undefined ? localImageUrl : printer.image_url;

  return (
    <div className="max-w-lg space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(`/printers/${id}`)} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Edit Printer</h1>
          <p className="text-sm text-muted-foreground">{printer.name}</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div>
          <Label className="mb-2 block">Printer Image</Label>
          <PrinterImageDropzone
            printerId={Number(id)}
            currentImageUrl={currentImageUrl}
            onUpdate={handleImageUpdate}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="name">Printer Name *</Label>
          <Input id="name" value={form.name} onChange={set('name')} required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="model">Model</Label>
            <Input id="model" value={form.model} onChange={set('model')} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="type">Type</Label>
            <Input id="type" value={form.type} onChange={set('type')} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="serial_number">Serial Number</Label>
            <Input id="serial_number" value={form.serial_number} onChange={set('serial_number')} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="location">Location</Label>
            <Input id="location" value={form.location} onChange={set('location')} />
          </div>
        </div>

        {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <div className="flex gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => navigate(`/printers/${id}`)}>Cancel</Button>
          <Button onClick={handleSave} isLoading={saving}>Save Changes</Button>
        </div>
      </div>

      <div className="rounded-lg border border-destructive/30 bg-card p-5">
        <h3 className="font-medium text-destructive mb-2">Danger Zone</h3>
        <p className="text-sm text-muted-foreground mb-3">Permanently remove this printer and all associated data.</p>
        <Button variant="destructive" size="sm" onClick={() => setShowDelete(true)}>Delete Printer</Button>
      </div>

      {showDelete && (
        <DeletePrinterDialog
          printer={printer}
          onClose={() => setShowDelete(false)}
          onDeleted={async () => {
            await refetchPrinters();
            navigate('/printers');
          }}
        />
      )}
    </div>
  );
}
