import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { ImageIcon, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface Props {
  printerId: number;
  currentImageUrl?: string | null;
  onUpdate: (imageUrl: string | null) => void;
}

export function PrinterImageDropzone({ printerId, currentImageUrl, onUpdate }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/printers/${printerId}/image`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUpdate(data.data.image_url);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    setLoading(true);
    try {
      await api.delete(`/printers/${printerId}/image`);
      onUpdate(null);
    } catch {
      setError('Failed to remove image');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      {currentImageUrl ? (
        <div className="relative w-32 h-32 rounded-lg overflow-hidden border">
          <img src={`${API_BASE}${currentImageUrl}`} alt="Printer" className="w-full h-full object-cover" />
          <button
            onClick={handleDelete}
            disabled={loading}
            className="absolute top-1 right-1 rounded-full bg-black/60 p-1 text-white hover:bg-black/80"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div
          onClick={() => fileRef.current?.click()}
          className="flex h-32 w-32 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed hover:border-primary hover:bg-muted/30 transition-colors"
        >
          <ImageIcon className="h-8 w-8 text-muted-foreground mb-1" />
          <span className="text-xs text-muted-foreground">Add image</span>
        </div>
      )}
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={loading}>
        <Upload className="mr-1.5 h-3.5 w-3.5" />
        {loading ? 'Uploading...' : currentImageUrl ? 'Replace' : 'Upload'}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
    </div>
  );
}
