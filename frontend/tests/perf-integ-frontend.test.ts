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
