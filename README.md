# Open Holdem Manager

Local poker hand history tracker for GGPoker Rush & Cash. Parses hand histories, stores in DuckDB, computes H2N-style stats, shows graphs.

**Website:** [ohm.antonchaynik.ru](https://ohm.antonchaynik.ru)

## Download

| Platform | Download |
|----------|----------|
| macOS (Apple Silicon) | [Open-Holdem-Manager.dmg](https://github.com/AHTOOOXA/open-holdem-manager/releases/latest/download/Open-Holdem-Manager-arm64.dmg) |
| Windows | [Open-Holdem-Manager-Setup.exe](https://github.com/AHTOOOXA/open-holdem-manager/releases/latest/download/Open-Holdem-Manager-Setup.exe) |

[All releases](https://github.com/AHTOOOXA/open-holdem-manager/releases)

> **macOS note:** The app is not code-signed yet. macOS will show "app is damaged and can't be opened." To fix, run in Terminal after installing:
> ```
> xattr -cr /Applications/Open\ Holdem\ Manager.app
> ```

## Development

```bash
make setup    # install deps
make dev      # starts backend (port 4243) + frontend (port 4242)
```

## Tech Stack

- **Backend**: Python, FastAPI, DuckDB
- **Frontend**: React, TypeScript, Vite, TailwindCSS, shadcn/ui, Recharts
- **Desktop**: Electron, electron-builder
