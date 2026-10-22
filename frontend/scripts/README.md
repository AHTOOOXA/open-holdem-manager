# Frontend scripts

## check-design.mjs (design-token ratchet)

Components must use the tokens in `src/index.css` (`@theme`) instead of raw colours and
arbitrary sizes. `npm run lint` runs ESLint and then this check.

Scanned: `src/**/*.{ts,tsx}` and `landing/**/*.{ts,tsx}` (not `*.d.ts`; only the top-level build folders `dist`, `dist-landing` and `node_modules` are skipped, so e.g. `components/distribution/` is scanned).
CSS files are not scanned. Comments are stripped before matching.

| Rule | Counts |
| --- | --- |
| `hex` | `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa` literals (not `#root`, URL anchors, `Hand #123`) |
| `color-fn` | `rgb(`, `rgba(`, `hsl(`, `hsla(`, `oklch(`, `oklab(`, `color-mix(` |
| `text-arbitrary` | `text-[12px]`, `text-[0.8rem]`, `text-[1.1em]` |
| `inline-color` | (1) in `style={{ ... }}`, keys `color`, `background`, `backgroundColor`, `borderColor`, `fill`, `stroke`, `outlineColor`, `boxShadow`, `textShadow` with a string-literal value (variables, `var(--x)`, `none`/`transparent`/`inherit`/`currentColor` are fine); (2) the same keys anywhere (plain objects) when the value is a bare CSS named colour (`'red'`, `'white'`, ...); (3) `border`/`borderTop|Right|Bottom|Left`/`outline` string values containing a hex, colour function or named colour (`'1px solid red'`; `var(--x)` and Tailwind class strings such as cva `outline:` variants are ignored); (4) JSX `fill=`, `stroke=`, `stopColor=`, `color=`, `floodColor=`, `lightingColor=` with a literal hex or named colour (`currentColor`, `none`, `var(--x)`, `url(#x)` are fine) |
| `toFixed` | `.toFixed(` calls |
| `palette` | Tailwind default-palette classes: `{text,bg,border,ring,outline,fill,stroke,from,via,to,decoration,divide,placeholder,caret,accent,shadow}-{red..stone}-{50..950}` with optional `/NN`, under any variant prefix (`hover:`, `dark:`, `data-[..]:`), plus `text-/bg-/border-` `white`/`black`. Token utilities (`text-money-pos`, `bg-tag-3`, `text-red` legacy alias) are not matched |

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

Known gaps: colours in plain JS objects are caught by `hex`/`color-fn`, and by `inline-color` only for the
listed keys with a bare named colour; arbitrary values (`bg-[red]`), colours built at runtime, and CSS
files are not scanned. JSX `color=` on a non-colour prop would be a false positive (use a token or rename).
