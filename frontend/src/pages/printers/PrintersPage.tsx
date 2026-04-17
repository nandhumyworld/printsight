import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useNavigate } from 'react-router-dom';
import { Printer, Plus, Upload, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Printer as PrinterType } from '@/types';

export default function PrintersPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['printers'],
    queryFn: () => api.get('/printers').then(r => r.data.data as PrinterType[]),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      api.put(`/printers/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['printers'] }),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-48 animate-pulse rounded bg-muted" />
        {[...Array(3)].map((_, i) => <div key={i} className="h-24 animate-pulse rounded-lg bg-muted" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Printers</h1>
          <p className="text-sm text-muted-foreground mt-1">{data?.length ?? 0} printer{data?.length !== 1 ? 's' : ''} registered</p>
        </div>
        <Button onClick={() => navigate('/printers/new')}>
          <Plus className="mr-2 h-4 w-4" />
          Add Printer
        </Button>
      </div>

      {!data || data.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed p-16 text-center">
          <Printer className="mx-auto mb-3 h-12 w-12 text-muted-foreground/40" />
          <h3 className="font-semibold text-lg">No printers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Add your first printer to start uploading CSV logs.</p>
          <Button className="mt-4" onClick={() => navigate('/printers/new')}>
            <Plus className="mr-2 h-4 w-4" />
            Add Printer
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((p) => (
            <div key={p.id} className="rounded-lg border bg-card p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <Printer className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-semibold">{p.name}</p>
                    {p.model && <p className="text-xs text-muted-foreground">{p.model}</p>}
                  </div>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${p.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {p.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              {(p.type || p.serial_number || p.location) && (
                <div className="text-xs text-muted-foreground space-y-0.5">
                  {p.type && <p>Type: {p.type}</p>}
                  {p.serial_number && <p>S/N: {p.serial_number}</p>}
                  {p.location && <p>Location: {p.location}</p>}
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1"
                  onClick={() => navigate(`/printers/${p.id}`)}
                >
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                  Upload CSV
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigate(`/printers/${p.id}/mapping`)}
                >
                  <Settings className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
