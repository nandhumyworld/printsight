import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import { CHART_PALETTE } from '@/lib/colors';

interface BreakdownPoint {
  date: string;
  paper_cost?: number;
  toner_cost?: number;
  total_cost?: number;
}

export function CostBreakdownChart({ data }: { data: BreakdownPoint[] }) {
  if (!data || data.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${v}`} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend />
        <Bar dataKey="paper_cost" name="Paper" fill={CHART_PALETTE[0]} radius={[3, 3, 0, 0]} />
        <Bar dataKey="toner_cost" name="Toner" fill={CHART_PALETTE[1]} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
