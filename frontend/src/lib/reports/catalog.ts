/** Split reports offered by the "+" (Select Report) picker: captions, groups and one-line descriptions. */
import type { SplitType } from './types';
import type { LowerTab } from './pages';

export const LOWER_TAB_CAPTION: Record<LowerTab, string> = {
  hands: 'Hands',
  results: 'Results',
  table_size: 'Table Size',
  next_actions: 'Next Actions',
  faced_next: 'Faced Next',
  hour_of_day: 'Hour of Day',
  positions: 'Positions',
  stack_sizes: 'Stack Sizes',
  bet_sizing: 'Bet Sizing',
};

export interface ReportGroup {
  title: string;
  items: { type: SplitType; description: string }[];
}

export const REPORT_GROUPS: readonly ReportGroup[] = [
  {
    title: 'Table',
    items: [
      { type: 'results', description: 'Results per stakes and table type.' },
      { type: 'table_size', description: 'Results by the number of seats at the table.' },
    ],
  },
  {
    title: 'Actions',
    items: [
      { type: 'next_actions', description: "Splits by hero's next decision." },
      { type: 'faced_next', description: "Splits by what the villains did right after hero's action." },
    ],
  },
  {
    title: 'Session',
    items: [{ type: 'hour_of_day', description: 'Stats per hour of the day.' }],
  },
  {
    title: 'Positions',
    items: [{ type: 'positions', description: 'Stats for each of the six 6-max positions.' }],
  },
  {
    title: 'Other',
    items: [
      { type: 'stack_sizes', description: "Results by hero's starting stack in big blinds." },
      { type: 'bet_sizing', description: 'Results by bet-size bucket of the current action.' },
    ],
  },
];
