interface KpiCardProps {
  title: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  gradient: string;
}

export function KpiCard({ title, value, sub, icon: Icon, gradient }: KpiCardProps) {
  return (
    <div className={`rounded-xl bg-gradient-to-br ${gradient} p-5 text-white shadow-sm`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-white/80">{title}</p>
        <div className="rounded-full bg-white/20 p-2">
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-3 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-white/70">{sub}</p>}
    </div>
  );
}
