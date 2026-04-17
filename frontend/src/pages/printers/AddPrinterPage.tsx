import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft } from 'lucide-react';

export default function AddPrinterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    model: '',
    type: '',
    serial_number: '',
    location: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(form).filter(([_, v]) => v.trim() !== '')
      );
      const { data } = await api.post('/printers', payload);
      navigate(`/printers/${data.data.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create printer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/printers')} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Add Printer</h1>
          <p className="text-sm text-muted-foreground">Register a new printer to track costs</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="name">Printer Name *</Label>
            <Input id="name" placeholder="e.g. HP LaserJet 1st Floor" value={form.name} onChange={set('name')} required />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="model">Model</Label>
              <Input id="model" placeholder="HP LaserJet Pro M404n" value={form.model} onChange={set('model')} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="type">Type</Label>
              <Input id="type" placeholder="Laser / Inkjet" value={form.type} onChange={set('type')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="serial_number">Serial Number</Label>
              <Input id="serial_number" placeholder="SN-XXXXX" value={form.serial_number} onChange={set('serial_number')} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="location">Location</Label>
              <Input id="location" placeholder="Office 2B" value={form.location} onChange={set('location')} />
            </div>
          </div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => navigate('/printers')}>Cancel</Button>
            <Button type="submit" isLoading={loading}>Create Printer</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
