import { useSearchParams } from 'react-router-dom';
import HandExplorer from '@/components/hands/HandExplorer';

export default function HandsPage() {
  const [searchParams] = useSearchParams();
  const initialStatFlags = searchParams.getAll('stat_flag');
  const urlStatKey = searchParams.get('stat_key') || undefined;
  const urlPosition = searchParams.get('position')?.toUpperCase();

  return (
    <HandExplorer
      fixedParams={{ stat_key: urlStatKey }}
      initialFilters={{
        position: urlPosition ? [urlPosition] : [],
        statFlags: initialStatFlags,
      }}
      header={<h1 className="text-[20px] font-bold text-text">Hands</h1>}
      className="max-w-[1600px] mx-auto px-2"
    />
  );
}
