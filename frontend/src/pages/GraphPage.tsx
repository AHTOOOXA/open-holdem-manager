import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { getGraphData } from '@/lib/api';
import type { GraphPoint } from '@/lib/api';

export default function GraphPage() {
  const [data, setData] = useState<GraphPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<'cumulative' | 'bb100'>('cumulative');

  useEffect(() => {
    getGraphData()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-text-muted">Loading graph...</p>;
  if (data.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-text-muted text-lg">No hands imported yet.</p>
        <p className="text-text-muted text-sm mt-2">Upload hand histories first.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Results Graph</h1>
        <div className="flex gap-2">
          <button
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              mode === 'cumulative'
                ? 'bg-primary text-white'
                : 'bg-surface border border-border text-text-muted hover:text-text'
            }`}
            onClick={() => setMode('cumulative')}
          >
            Cumulative BB
          </button>
          <button
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              mode === 'bb100'
                ? 'bg-primary text-white'
                : 'bg-surface border border-border text-text-muted hover:text-text'
            }`}
            onClick={() => setMode('bb100')}
          >
            BB/100 Rolling
          </button>
        </div>
      </div>

      <div className="bg-surface rounded-lg border border-border p-4">
        <ResponsiveContainer width="100%" height={500}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
            <XAxis
              dataKey="hand_number"
              stroke="#8888a0"
              tick={{ fontSize: 12 }}
              label={{ value: 'Hands', position: 'insideBottom', offset: -5, fill: '#8888a0' }}
            />
            <YAxis
              stroke="#8888a0"
              tick={{ fontSize: 12 }}
              label={{
                value: mode === 'cumulative' ? 'BB Won' : 'BB/100',
                angle: -90,
                position: 'insideLeft',
                fill: '#8888a0',
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#12121a',
                border: '1px solid #2a2a3a',
                borderRadius: '8px',
                color: '#e4e4ef',
              }}
              formatter={(value: number) => [value.toFixed(2), mode === 'cumulative' ? 'BB' : 'BB/100']}
              labelFormatter={(label) => `Hand #${label}`}
            />
            <ReferenceLine y={0} stroke="#8888a0" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey={mode === 'cumulative' ? 'cumulative_bb' : 'bb_per_100_rolling'}
              stroke="#6366f1"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div className="text-2xl font-bold font-mono">{data.length.toLocaleString()}</div>
          <div className="text-xs text-text-muted">Hands</div>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div
            className={`text-2xl font-bold font-mono ${
              data[data.length - 1].cumulative_bb >= 0 ? 'text-green' : 'text-red'
            }`}
          >
            {data[data.length - 1].cumulative_bb.toFixed(1)}
          </div>
          <div className="text-xs text-text-muted">Total BB</div>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div
            className={`text-2xl font-bold font-mono ${
              (data[data.length - 1].bb_per_100_rolling ?? 0) >= 0 ? 'text-green' : 'text-red'
            }`}
          >
            {data[data.length - 1].bb_per_100_rolling?.toFixed(2) ?? '-'}
          </div>
          <div className="text-xs text-text-muted">Current BB/100</div>
        </div>
      </div>
    </div>
  );
}
