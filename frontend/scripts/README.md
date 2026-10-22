# Frontend scripts

## check-design.mjs (design-token ratchet)

Components must use the tokens in `src/index.css` (`@theme`) instead of raw colours and
arbitrary sizes. `npm run lint` runs ESLint and then this check.

Scanned: `src/**/*.{ts,tsx}` and `landing/**/*.{ts,tsx}` (not `*.d.ts`, `node_modules`, `dist*`).
CSS files are not scanned. Comments are stripped before matching.

| Rule | Counts |
| --- | --- |
| `hex` | `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa` literals (not `#root`, URL anchors, `Hand #123`) |
| `color-fn` | `rgb(`, `rgba(`, `hsl(`, `hsla(`, `oklch(`, `oklab(`, `color-mix(` |
| `text-arbitrary` | `text-[12px]`, `text-[0.8rem]`, `text-[1.1em]` |
| `inline-color` | in `style={{ ... }}`, keys `color`, `background`, `backgroundColor`, `borderColor`, `fill`, `stroke`, `outlineColor`, `boxShadow`, `textShadow` with a string-literal value (variables, `var(--x)`, `none`/`transparent`/`inherit`/`currentColor` are fine) |
| `toFixed` | `.toFixed(` calls |

### Ratchet

`design-baseline.json` holds the current per-file, per-rule counts. A file may never exceed its
baseline count; files not in the baseline start at zero. `design-allow.json` lists path prefixes
exempt from specific rules (with reasons); keep it short.

- `npm run lint:design` checks (exit 1 on any file/rule above baseline, prints offending lines).
  It also lists files that dropped below baseline.
- `npm run lint:design:update` rewrites the baseline after you cleaned something up. It refuses
  to raise a count or add a file with violations; `-- --allow-increase` overrides (reviewer beware).

### Fixing a failure

- Colours: use a token class (`text-green`, `bg-surface`, ...) or `var(--color-...)` from `src/index.css`.
  Add a token there if one is missing, rather than a literal.
- Font sizes: use the scale (`text-xs`, `text-sm`, ...) or a named token.
- Numbers: use the helpers in `src/lib/format/` instead of `.toFixed(`.
- Inline styles: prefer classes; if the value is dynamic, pass a variable or `var(--...)`.

Known gaps: colours in plain JS objects outside `style={{}}` are only caught by `hex`/`color-fn`;
named colours (`'red'`) are only caught inside inline style keys.
