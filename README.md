# ipsw-storage

`ipsw-storage` is a small Python CLI for listing Apple IPSW firmware records
from the [ipsw.me](https://ipsw.me) API and [AppleDB](https://appledb.dev), and
for interactively downloading selected firmware.

## Installation

```bash
python -m pip install .
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

The interactive `pull` and `devices --interactive` commands shell out to
[`fzf`](https://github.com/junegunn/fzf) — install it separately if you want
terminal selection.

## Usage

### List firmware

Firmware records are merged from ipsw.me and AppleDB by default. Pick a single
source with `--source`:

```bash
ipsw-storage list
ipsw-storage list --source ipsw
ipsw-storage list --source appledb
```

Filter to signed firmware for one device:

```bash
ipsw-storage list --device iPhone16,2 --signed-only
```

Machine-readable output:

```bash
ipsw-storage list --device iPhone16,2 --json-output
```

### Browse devices (AppleDB)

List every AppleDB device, including simulators and internal identifiers:

```bash
ipsw-storage devices
ipsw-storage devices --type Simulator
ipsw-storage devices --device iPhone99,11
```

Pick a device interactively with `fzf` and print its summary:

```bash
ipsw-storage devices --interactive
```

### AppleDB metadata

Show a single device or OS build:

```bash
ipsw-storage appledb device iPhone16,2
ipsw-storage appledb firmware iOS 22A3354
```

### Download an IPSW

Interactively select and download a firmware. The fzf picker shows merged
records from both sources by default:

```bash
ipsw-storage pull ./downloads --device iPhone16,2 --signed-only
```

To browse AppleDB devices first, then pick firmware for the chosen device:

```bash
ipsw-storage pull ./downloads --pick-device
```

Skip fzf entirely by pinning to a specific firmware — when `--device` /
`--version` / `--build` narrow the catalog to a single record, `pull`
downloads it directly:

```bash
ipsw-storage pull ./downloads --device iPhone99,11 --version 26.1
ipsw-storage pull ./downloads --device iPhone99,11 --build 23B85
```

If the filter still matches multiple records (e.g. one version with several
builds) `pull` falls back to fzf so you can pick the right one.

Downloads show a progress bar with transferred size, speed, and ETA.

You can also run the package module directly:

```bash
python -m ipsw_storage list --signed-only
```

## Module layout

| Module                       | Responsibility                                                  |
|------------------------------|-----------------------------------------------------------------|
| `ipsw_storage.api`           | Orchestrator: `Firmware` type, `fetch_ipsws`, `AGENTS` registry |
| `ipsw_storage.api.ipsw_me`   | ipsw.me agent (`NAME = "ipsw"`)                                 |
| `ipsw_storage.api.appledb`   | AppleDB agent (`NAME = "appledb"`) + device/build metadata      |
| `ipsw_storage.api.types`     | Shared `Firmware` / `FirmwareSource` types                      |
| `ipsw_storage.download`      | Streaming file download with progress callbacks                 |
| `ipsw_storage.cli`           | `click` command surface                                         |

### Agent contract

Every API agent under `ipsw_storage.api` exposes the same two symbols:

```python
NAME: str  # "ipsw", "appledb", ...
def fetch_ipsws(
    device: str | None = None,
    *,
    signed_only: bool = False,
) -> list[Firmware]: ...
```

The orchestrator in `ipsw_storage.api.fetch_ipsws` looks up agents by
`AGENTS[name]`, calls each one with the same arguments, then merges, dedupes,
and sorts the combined result. Adding a new source means dropping a new module
into `ipsw_storage/api/` that conforms to this contract.

## Development

Run the checks used by CI:

```bash
python -m ruff check .
python -m pytest
python -m build
```

### Versioning

The package version is derived from git via
[`setuptools_scm`](https://github.com/pypa/setuptools_scm). Tag a release as
`vX.Y.Z` and the next build wheel will pick that up automatically — no need to
edit `pyproject.toml`. Between tags, dev builds get a PEP 440-compliant
`X.Y.Z.devN+g<sha>` suffix.

`setuptools_scm` writes the resolved value to `ipsw_storage/_version.py` at
build time; that file is gitignored. At runtime, `ipsw_storage.__version__`
reads from it (or falls back to `importlib.metadata` for installed wheels).

## License

This project is released under the [Mozilla Public License 2.0](LICENSE).
