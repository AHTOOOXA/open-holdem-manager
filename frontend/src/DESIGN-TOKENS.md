# OHM design tokens

One token layer in `src/index.css` drives every screen. Components use the **roles** below as
Tailwind utilities (`bg-surface-sunken`, `text-money-pos`, `rounded-control`, `h-row-dense` …), never
raw colours or pixel font sizes. Values live in `:root`; the `@theme inline` block maps them to
utilities. Dark only for now: `<html class="dark">`, so shadcn's `dark:` variants apply. A light theme
would be a second `:root`-style block.

Live gallery: run the app and open `/design` (not in the sidebar).

## Identity

- Stone neutrals, amber accent (`--primary`), lucide icons.
- **Geist Sans** for all UI text, with tabular figures on `body` so numbers line up in columns.
- **GeistMono** (`font-mono`) only for raw hand histories, hand ids and code-like text.

## Colour roles

| Role | Utility | Use |
|---|---|---|
| App background | `bg-background` | behind everything |
| Panel | `bg-card` | pages, grids, cards |
| Sunken | `bg-surface-sunken` | inputs, alternate bands, wells |
| Raised | `bg-surface-raised`, `bg-popover` | popups, menus, dialogs |
| Text 1 / 2 / 3 | `text-foreground` / `text-muted-foreground` / `text-subtle-foreground` | values and headings / labels / inactive, placeholders, "--" |
| Borders | `border-border` / `border-border-subtle` | rules, dividers |
| Hover / selected / focus | `bg-overlay-hover` / `bg-overlay-selected` / `bg-overlay-focus` | layered over any surface |
| Data selection | `bg-selection` + `ring-primary` | selected cell, row, segment |
| Accent | `bg-primary`, `text-primary` | primary action, active tab indicator, focus ring |
| Money + / − / 0 | `text-money-pos` / `text-money-neg` / `text-money-zero` | via `moneyClass(v, digits)` from `lib/format` |
| Sample size | `text-sample` | small trailing sample counts |
| Positions | `text-pos-ep` … `text-pos-bb` | one palette everywhere |
| Streets | `text-street-flop` / `-turn` / `-river` | |
| Actions | `text-act-fold` / `-check` / `-call` / `-bet` / `-raise` / `-allin` | one meaning in every view |
| Suits | `bg-suit-s` / `-h` / `-d` / `-c` | card tiles, white rank text |
| Chart series | `--chart-main`, `--chart-ev`, `--chart-sd`, `--chart-nsd`, `--chart-rake`, `--chart-axis`, `--chart-grid` | via `lib/chart-theme.ts` |
| Tags and markers | `bg-tag-1` … `bg-tag-9` | hand tags, player colours, workspaces |
| Hand-value categories | `--hv-<category>` | via `hvColor(key)` |

Every colour that carries text or data is at least 4.5:1 on `card` (`subtle-foreground` is the
lowest at 4.8). Low-sample values are shown in `text-subtle-foreground`, not by lowering opacity.

Legacy names (`text-text`, `text-text-muted`, `bg-surface`, `bg-surface-hover`, `text-green`,
`text-red`, `text-yellow`, `text-blue`) are aliases of the roles above. Don't use them in new code.

## Type scale

| Utility | Size / line | Use |
|---|---|---|
| `text-2xs` | 10 / 14 | sample counts, badges |
| `text-label` | 11 / 16 | small labels, section headers |
| `text-xs` | 12 / 16 | secondary cells, chips |
| `text-cell` | 13 / 18 | dense grids |
| `text-sm` | 14 / 20 | body text, controls, main grids |
| `text-base` / `text-lg` / `text-xl` | 16 / 18 / 20 | headings |

## Shape, density, layers

- Radii: `rounded-cell` 2px (grid cells, bars), `rounded-control` 4px (buttons, inputs, tabs, menus),
  `rounded-card` 8px (cards, dialogs), `rounded-pill` (chips).
- Spacing: 8px is the unit (`gap-2`, `px-2`); 4px for tight gaps (`gap-1`); 12px between stacked
  blocks (`gap-3`); 16px cell side padding (`px-4`); 24px page gutter (`p-6`).
- Heights: `h-row-dense` 26px (dense grids), `h-row` 30px (lists, menus), `h-row-tree` 32px,
  `h-row-header` 28px, `h-control` 28px (inputs, selects, chips), `h-button` 30px.
- Layers: `z-(--z-sticky)` 10, `z-(--z-dropdown)` 50, `z-(--z-modal)` 100, `z-(--z-popover)` 110,
  `z-(--z-toast)` 200.
- Motion: hover is instant; indicators and selection fade over `--motion-fast` (150ms);
  `prefers-reduced-motion` turns transitions off.

## Numbers

All formatting goes through `src/lib/format/`: one rounding rule (round half to even), k/m
shortening, signed money, `moneyTone` / `moneyClass` with an explicit zero rule, and the stat
notation rules in `format/h2n.ts`. Don't call `.toFixed` in components.

## Shared primitives

`StatValue` (value + sample with the one sample rule), `Chip` (filter chips, tags, badges; keyboard
reachable remove button), line `Tabs` with an overflow menu. Data grids and page chains follow.

## Guardrail

`npm run lint` runs `scripts/check-design.mjs`: a per-file ratchet over hex and `rgb()/oklch()`
literals, arbitrary `text-[Npx]`, colour-valued inline styles and `.toFixed(`. Counts may only go
down; new files start at zero. Details in `scripts/README.md`.
