const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface Props {
  printer: { name: string; model?: string | null; image_url?: string | null };
}

export function PrinterHeroBanner({ printer }: Props) {
  const heroImage = printer.image_url ? `${API_BASE}${printer.image_url}` : null;
  return (
    <div
      className="relative flex h-32 items-end overflow-hidden rounded-xl bg-gradient-to-r from-slate-800 to-slate-600 px-6 pb-4"
      style={heroImage ? { backgroundImage: `url(${heroImage})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}
    >
      <div className="absolute inset-0 bg-black/50 rounded-xl" />
      <div className="relative z-10">
        <h1 className="text-2xl font-bold text-white">{printer.name}</h1>
        {printer.model && <p className="text-sm text-white/70">{printer.model}</p>}
      </div>
    </div>
  );
}
