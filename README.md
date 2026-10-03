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
> Before you do that, [verify your download](#verify-your-download).

### Verify your download

Binaries are not code-signed yet, so check that the file was built by this repository's GitHub Actions from a tagged commit. With the [GitHub CLI](https://cli.github.com):

```bash
gh attestation verify Open-Holdem-Manager-arm64.dmg --repo AHTOOOXA/open-holdem-manager
```

Or compare the checksum with `SHA256SUMS.txt` from the same release:

```bash
shasum -a 256 Open-Holdem-Manager-arm64.dmg                    # macOS
Get-FileHash Open-Holdem-Manager-Setup.exe -Algorithm SHA256   # Windows PowerShell
```

## Privacy & network

Your hand histories and database stay on your computer. There is no account, no telemetry and no analytics. The app makes these network requests:

| When | Where | What is sent |
|---|---|---|
| On start and every 4 hours | GitHub (`api.github.com` on macOS, release files on Windows) | A normal HTTPS request to check for a newer version. No hand data. |
| You click **Download** on an update (Windows) | GitHub release files | Downloads the installer. Nothing is installed until you click **Restart to update**. |
| You click **Share** on a hand | Nothing at first | A link to `ohm.antonchaynik.ru` with the hand encoded inside it is copied to your clipboard. Whoever opens that link sends the hand to the website. Turn on anonymize first to hide your opponents' names; your own name stays. |

The local backend listens on `127.0.0.1` only.

## Security

See [SECURITY.md](SECURITY.md) for how releases are built and how to report a vulnerability privately.

## Development

```bash
make setup    # install deps
make dev      # starts backend (port 4243) + frontend (port 4242)
```

## Tech Stack

- **Backend**: Python, FastAPI, DuckDB
- **Frontend**: React, TypeScript, Vite, TailwindCSS, shadcn/ui, Recharts
- **Desktop**: Electron, electron-builder

## License

Copyright © 2025-2026 Anton Safonov.

Open Holdem Manager is free software under the [GNU Affero General Public License v3.0](LICENSE). You can use, study, modify and share it. If you distribute a modified version, or run one as a network service, you must publish its source under the same license.
