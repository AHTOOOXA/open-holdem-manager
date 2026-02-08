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
  Legend,
} from 'recharts';
import { getGraphData } from '@/lib/api';
import type { GraphPoint } from '@/lib/api';

export default function GraphPage() {
  const [data, setData] = useState<GraphPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<'cumulative' | 'bb100'>('cumulative');
  const [showEV, setShowEV] = useState(true);

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

  const last = data[data.length - 1];
  const hasEVData = data.some(d => d.cumulative_ev_bb !== d.cumulative_bb);

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Results Graph</h1>
        <div className="flex gap-2 items-center">
          {hasEVData && (
            <button
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                showEV
                  ? 'bg-yellow-600 text-white'
                  : 'bg-surface border border-border text-text-muted hover:text-text'
              }`}
              onClick={() => setShowEV(!showEV)}
            >
              EV Line
            </button>
          )}
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
              formatter={(value: number, name: string) => [
                value.toFixed(2),
                name === 'cumulative_bb' ? 'BB' :
                name === 'cumulative_ev_bb' ? 'EV BB' :
                name === 'bb_per_100_rolling' ? 'BB/100' :
                name === 'ev_bb_per_100_rolling' ? 'EV BB/100' : name,
              ]}
              labelFormatter={(label) => `Hand #${label}`}
            />
            <ReferenceLine y={0} stroke="#8888a0" strokeDasharray="3 3" />
            {hasEVData && <Legend />}
            <Line
              type="monotone"
              dataKey={mode === 'cumulative' ? 'cumulative_bb' : 'bb_per_100_rolling'}
              name={mode === 'cumulative' ? 'Actual' : 'BB/100'}
              stroke="#6366f1"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
            {showEV && hasEVData && (
              <Line
                type="monotone"
                dataKey={mode === 'cumulative' ? 'cumulative_ev_bb' : 'ev_bb_per_100_rolling'}
                name={mode === 'cumulative' ? 'All-in EV' : 'EV BB/100'}
                stroke="#eab308"
                strokeWidth={2}
                dot={false}
                connectNulls
                strokeDasharray="6 3"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-5 gap-4">
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div className="text-2xl font-bold font-mono">{data.length.toLocaleString()}</div>
          <div className="text-xs text-text-muted">Hands</div>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div
            className={`text-2xl font-bold font-mono ${
              last.cumulative_bb >= 0 ? 'text-green' : 'text-red'
            }`}
          >
            {last.cumulative_bb.toFixed(1)}
          </div>
          <div className="text-xs text-text-muted">Total BB</div>
        </div>
        {hasEVData ? (
          <div className="bg-surface rounded-lg border border-border p-4 text-center">
            <div
              className={`text-2xl font-bold font-mono ${
                last.cumulative_ev_bb >= 0 ? 'text-green' : 'text-red'
              }`}
            >
              {last.cumulative_ev_bb.toFixed(1)}
            </div>
            <div className="text-xs text-text-muted">EV BB</div>
          </div>
        ) : (
          <div className="bg-surface rounded-lg border border-border p-4 text-center">
            <div
              className={`text-2xl font-bold font-mono ${
                (last.bb_per_100_rolling ?? 0) >= 0 ? 'text-green' : 'text-red'
              }`}
            >
              {last.bb_per_100_rolling?.toFixed(2) ?? '-'}
            </div>
            <div className="text-xs text-text-muted">BB/100</div>
          </div>
        )}
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div className="text-2xl font-bold font-mono text-red">
            {last.cumulative_rake_bb.toFixed(1)}
          </div>
          <div className="text-xs text-text-muted">Rake (BB)</div>
        </div>
        <div className="bg-surface rounded-lg border border-border p-4 text-center">
          <div className="text-2xl font-bold font-mono text-text-muted">
            {data.length > 0 ? (last.cumulative_rake_bb / data.length * 100).toFixed(2) : '-'}
          </div>
          <div className="text-xs text-text-muted">Rake/100</div>
        </div>
      </div>
    </div>
  );
}
