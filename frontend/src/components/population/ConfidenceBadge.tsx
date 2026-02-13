export default function ConfidenceBadge({ sample }: { sample: number }) {
  if (sample < 50) return null;

  let color: string;
  if (sample >= 1000) {
    color = 'bg-emerald-500/20 text-emerald-400';
  } else if (sample >= 200) {
    color = 'bg-yellow-500/20 text-yellow-400';
  } else {
    color = 'bg-red-500/20 text-red-400';
  }

  return (
    <span className={`inline-flex items-center px-1 py-0 rounded text-[10px] font-mono ${color}`}>
      {sample >= 1000 ? '1k+' : sample}
    </span>
  );
}
