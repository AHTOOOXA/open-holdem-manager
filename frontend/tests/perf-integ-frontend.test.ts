// Frontend integration of the performance pass (round 2): heavy queries carry the query policy and
// hand react-query's AbortSignal to fetch, so a superseded or abandoned seconds-long request is cancelled.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { getGraphData, getResultsBreakdown, setWorkspaceIdGetter } from '../src/lib/api';

const SRC = path.join(import.meta.dirname, '..', 'src');
const read = (rel: string) => fs.readFileSync(path.join(SRC, rel), 'utf8');

function captureFetch(): { calls: { url: string; init?: RequestInit }[]; restore: () => void } {
  const calls: { url: string; init?: RequestInit }[] = [];
  const orig = globalThis.fetch;
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify({ points: [], sessions: [] }), { status: 200 });
  }) as typeof fetch;
  return { calls, restore: () => { globalThis.fetch = orig; } };
}

test('getGraphData and getResultsBreakdown pass the AbortSignal to fetch', async () => {
  setWorkspaceIdGetter(() => 2);
  const f = captureFetch();
  try {
    const ac = new AbortController();
    await getGraphData({ chain: [], player_id: 9 }, ac.signal);
    await getResultsBreakdown({ stakes: '0.25' }, ac.signal);
    await getGraphData();
    assert.equal(f.calls[0].init?.signal, ac.signal);
    assert.match(f.calls[0].url, /\/reports\/graph\?chain=.*player_id=9.*workspace_id=2/);
    assert.equal(f.calls[1].init?.signal, ac.signal);
    assert.match(f.calls[1].url, /\/reports\/breakdown\?stakes=0\.25/);
    assert.equal(f.calls[2].init?.signal, undefined);
  } finally {
    f.restore();
  }
});

test('General fetchers forward the signal (api-general reads import.meta.env, so checked in source)', () => {
  const s = read('lib/api-general.ts');
  assert.match(s, /getGeneral\(params: GeneralFilterParams = \{\}, signal\?: AbortSignal\)/);
  assert.match(s, /\/general\?\$\{filterSearchParams\(params\)\}`, \{ signal \}\)/);
  assert.match(s, /\/detail\?\$\{filterSearchParams\(params\)\}`,\s*\{ signal \},/);
  assert.match(s, /\/hands\?\$\{sp\}`, \{ signal \}\)/);
});

/** Every heavy query site: spreads HEAVY_QUERY and passes react-query's signal to its fetcher. */
const HEAVY_SITES: Record<string, number> = {
  'components/reports/ReportsDashboard.tsx': 1,
  'components/reports/SplitReport.tsx': 1,
  'components/reports/tabs/StatsTab.tsx': 1,
  'components/reports/tabs/GraphTab.tsx': 1,
  'components/reports/tabs/PreflopRangeTab.tsx': 1,
  'components/reports/tabs/HandStrengthTab.tsx': 1,
  'components/reports/PlayerDialog.tsx': 1,
  'pages/GraphPage.tsx': 2,
  'components/statistics/DashboardView.tsx': 1,
  'components/general/StatPopup.tsx': 2,
  'components/general/GeneralHandList.tsx': 1,
  'components/sessions/SessionStats.tsx': 1,
  'components/stats/StatDetailPanel.tsx': 1,
  'pages/PopulationPage.tsx': 3,
  'pages/ComparePage.tsx': 1,
  'pages/StatsPage.tsx': 1,
  'pages/CashDropPage.tsx': 1,
  'pages/PlayersPage.tsx': 1,
  'pages/PlayerProfilePage.tsx': 3,
  'pages/IdentityDetailPage.tsx': 1,
  'hooks/useDrift.ts': 1,
};

test('heavy queries are tagged with the query policy and cancellable', () => {
  for (const [rel, n] of Object.entries(HEAVY_SITES)) {
    const s = read(rel);
    assert.match(s, /import \{ HEAVY_QUERY \} from '@\/lib\/query-policy';/, rel);
    assert.equal(s.split('...HEAVY_QUERY,').length - 1, n, `${rel}: HEAVY_QUERY spreads`);
    // no heavy fetcher is called without the signal
    assert.doesNotMatch(
      s,
      /queryFn: \(\) => (getSpot|getSplit|getGraphData|getResultsBreakdown|getPreflopRange|getHandStrength|getGeneral|getCellDetail|getHeroStats|getPlayerStats|getIdentityStats|getHeadToHead|getPopulation\w+|fetchCompareStats|getCashDropStats|getDrift|getStatDetailHands|getPlayers)\(/,
      rel,
    );
  }
});

test('hand lists are heavy only over a Reports chain', () => {
  const s = read('components/hands/HandExplorer.tsx');
  assert.match(s, /\.\.\.\(handsQueryParams\.chain !== undefined \? HEAVY_QUERY : \{\}\),/);
  assert.match(s, /queryFn: \(\{ signal \}\) => getHands\(handsQueryParams, signal\)/);
});

test('a mark in the General drawer refetches nothing beyond what useMarkHand already does', () => {
  // useMarkHand invalidates ['general', 'hands'] itself; a second invalidation (or one of every
  // ['general'] query) from the drawer callback would refetch the grid / popup for nothing.
  assert.doesNotMatch(read('components/general/GeneralHandList.tsx'), /onTagsChanged|invalidateQueries/);
  assert.match(read('components/marked/useMarkHand.ts'), /invalidateQueries\(\{ queryKey: \['general', 'hands'\] \}\)/);
});

test('Reports loads the Graph tab (and the charting chunk) on demand only', () => {
  const s = read('components/reports/ReportPageView.tsx');
  assert.doesNotMatch(s, /^import .*GraphTab/m);
  assert.doesNotMatch(s, /from 'recharts'|ResultsChart/);
  assert.match(s, /lazy\(loadGraphTab\)/);
  assert.match(s, /const loadGraphTab = \(\) => import\('\.\/tabs\/GraphTab'\);/);
});

test('the Statistics grid refetches on return when invalidated, a valid cached grid does not', async () => {
  assert.match(read('components/statistics/DashboardView.tsx'), /refetchOnMount: \(q\) => q\.state\.isInvalidated,/);

  // Why: a post-import refetch that consumes the signal is cancelled with revert when the screen is
  // left, so the query keeps its old data with isInvalidated still set. refetchOnMount: false would
  // then show the old grid (behind the chip) forever; the function form refetches it once.
  const { QueryClient, QueryObserver } = await import('@tanstack/query-core');
  const qc = new QueryClient();
  const key = ['general', 'grid', {}];
  let calls = 0;
  const queryFn = ({ signal }: { signal: AbortSignal }) => {
    calls += 1;
    return new Promise<string>((resolve, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason));
      setTimeout(() => resolve(`fresh${calls}`), 20);
    });
  };
  const opts = (refetchOnMount: boolean | ((q: { state: { isInvalidated: boolean } }) => boolean)) =>
    ({ queryKey: key, queryFn, staleTime: Infinity, refetchOnWindowFocus: false, retry: 0, refetchOnMount }) as never;
  qc.setQueryData(key, 'old');

  // Valid cached grid: no request on mount
  const idle = new QueryObserver(qc, opts((q) => q.state.isInvalidated));
  idle.subscribe(() => {})();
  assert.equal(calls, 0);

  // Data changed on screen: refetch starts, the user leaves before it ends
  const onScreen = new QueryObserver(qc, opts((q) => q.state.isInvalidated));
  const leave = onScreen.subscribe(() => {});
  void qc.invalidateQueries({ queryKey: ['general'] });
  assert.equal(calls, 1);
  leave();
  await new Promise((r) => setTimeout(r, 0));
  const state = qc.getQueryState(key)!;
  assert.equal(state.data, 'old');
  assert.equal(state.isInvalidated, true);

  // Back on the screen: false keeps the old grid, the policy refetches it
  const stale = new QueryObserver(qc, opts(false));
  stale.subscribe(() => {})();
  assert.equal(calls, 1);
  const back = new QueryObserver(qc, opts((q) => q.state.isInvalidated));
  const off = back.subscribe(() => {});
  assert.equal(calls, 2);
  await new Promise((r) => setTimeout(r, 40));
  assert.equal(qc.getQueryData(key), 'fresh2');
  assert.equal(qc.getQueryState(key)!.isInvalidated, false);
  off();
  qc.clear();
});
