# Mac Tinker Lab

**Mac Tinker Lab** is a collection of small, individually runnable Python experiments for learning how a MacBook works from the inside out. It is intentionally closer to a tray of screwdrivers than a single large application: each script does one job, shows its work, and can be read, modified, and rerun.

> **Safety model:** The tools are read-only by default. A report is like looking through a car window at the engine. It can tell you what is there, but it does not delete files, change settings, unload services, or “clean” anything automatically.

The repository already contains the CPR Console. The Mac Tinker Lab lives beside it and does not replace the existing market-research application.

## Start here

From the repository root, run a tool directly:

```bash
python3 tools/system_snapshot.py
python3 tools/large_files.py ~/Downloads --count 10
python3 tools/duplicate_finder ~/Documents --min-size 1M
python3 tools/hash_lab.py --text "hello tinkering"
```

Ask any tool for help:

```bash
python3 tools/network_snapshot.py --help
```

Most tools accept `--json`. Human output is for reading; JSON output is for piping into another program or inspecting with a text editor:

```bash
python3 tools/storage_overview.py --json | python3 -m json.tool
```

No third-party package is needed for the first 38 tools. The two image tools use Pillow only if you want image experiments:

```bash
python3 -m pip install Pillow
```

The scripts are designed to run on macOS. Several general-purpose tools also work on Linux, while macOS-only tools explain when they are unavailable rather than pretending that another operating system is a Mac.

## The mental model: your Mac as a small city

A useful beginner analogy is to picture your MacBook as a city. The **CPU** is the workforce, **memory** is the desk space available to workers, **storage** is the warehouse, **network interfaces** are roads, **DNS** is the phone book, **applications** are businesses, **property lists** are forms, and **launchd** is the city’s dispatcher that starts background services.

Python is the clipboard and measuring tape. It can ask the operating system questions, organize the answers, and make a repeatable experiment. The shared helper module uses Python’s standard library—`pathlib` for paths, `subprocess` for carefully invoking built-in commands, `plistlib` for Apple property lists, `sqlite3` for read-only database inspection, and `hashlib` for fingerprints.

## Tool catalog

| # | Tool | What it teaches | Typical experiment |
|---:|---|---|---|
| 1 | `system_snapshot` | Hardware and OS discovery | Compare Python’s view with `system_profiler`. |
| 2 | `storage_overview` | Filesystem capacity | See how a full disk changes free space. |
| 3 | `battery_report` | Power state observation | Compare charging and battery output. |
| 4 | `power_profile` | Power-management settings | Observe battery and adapter profiles. |
| 5 | `process_top` | Process inspection | Find which programs are busiest. |
| 6 | `network_snapshot` | Interfaces, routes, DNS | Map the roads out of your Mac. |
| 7 | `wifi_details` | Wi-Fi association | Inspect the current wireless link. |
| 8 | `dns_probe` | Name resolution | Compare a hostname with its IP addresses. |
| 9 | `port_check` | TCP connectivity | Test a service you own or a local server. |
| 10 | `url_headers` | HTTP protocol basics | See status, content type, and caching headers. |
| 11 | `disk_space_watch` | Time-series polling | Watch free space over several samples. |
| 12 | `large_files` | Filesystem traversal | Find large files without deleting them. |
| 13 | `duplicate_finder` | Hashing and deduplication | Find byte-for-byte duplicates. |
| 14 | `file_age_report` | File timestamps | Group files by how old they are. |
| 15 | `folder_tree` | Recursive data structures | Print a small tree of a folder. |
| 16 | `metadata_inspector` | Spotlight metadata | Explore a file’s indexed attributes. |
| 17 | `quarantine_inspector` | Extended attributes | Inspect download-quarantine markers. |
| 18 | `plist_inspector` | Structured configuration | Read Apple `.plist` files as Python objects. |
| 19 | `launchd_inventory` | macOS service scopes | See user and system launch-agent files. |
| 20 | `launchd_plist_linter` | Validation and schemas | Check common launchd keys without loading a job. |
| 21 | `app_inventory` | Application bundles | Read app names, identifiers, and versions. |
| 22 | `brew_inventory` | Package management | Inspect Homebrew formulae, casks, and outdated items. |
| 23 | `git_repo_health` | Version-control state | Summarize branch, status, and recent commits. |
| 24 | `dev_workspace_cleaner` | Build artifacts | Report cache folders and their sizes; never remove them. |
| 25 | `python_env_report` | Interpreter environments | Learn which Python and packages are active. |
| 26 | `package_size_report` | Dependency footprint | Estimate installed package sizes. |
| 27 | `clipboard_peek` | macOS pasteboard | Read a bounded clipboard sample; do not store it. |
| 28 | `quicklook_helper` | Command-line previews | Generate a thumbnail into a chosen output folder. |
| 29 | `screenshot_capture` | GUI-to-script bridges | Capture a screen only when explicitly requested. |
| 30 | `xattr_inventory` | Filesystem metadata | List extended attributes. |
| 31 | `defaults_inspector` | Preference domains | Read preferences without writing them. |
| 32 | `app_support_report` | Per-user application data | Find large support folders for inspection. |
| 33 | `hash_lab` | Integrity fingerprints | Hash a file or a piece of text. |
| 34 | `json_flatten` | Recursive transformation | Turn nested JSON into dotted paths. |
| 35 | `csv_profile` | Data quality | Count missing and unique values. |
| 36 | `markdown_link_checker` | Static analysis | Find missing local Markdown links. |
| 37 | `regex_lab` | Pattern matching | Display matches and character spans. |
| 38 | `text_diff_lab` | Change detection | Produce a unified diff for two text files. |
| 39 | `sqlite_inspector` | Relational data | Inspect tables and counts in read-only mode. |
| 40 | `image_contact_sheet` | Image composition | Build a labeled thumbnail grid. |
| 41 | `exif_inspector` | Image metadata | Read dimensions and EXIF fields. |
| 42 | `file_watch` | Event-like polling | Report files created, removed, or changed. |
| 43 | `speak_text` | Text-to-speech | Hear a phrase with the built-in `say` command. |
| 44 | `open_in_app` | App and URL automation | Ask macOS to open a target in a selected app. |
| 45 | `clipboard_put` | Pasteboard writing | Explicitly place text on the clipboard. |
| 46 | `calendar_month` | Dates and formatting | Render a month and validate a day. |
| 47 | `unicode_inspector` | Character encoding | Explore code points, names, and normalization. |
| 48 | `url_encode_lab` | Web encoding | Encode and decode query text. |
| 49 | `base64_lab` | Binary-to-text encoding | See how bytes become Base64 text. |
| 50 | `bytes_viewer` | Binary forensics | View a safe prefix of a file as hex. |
| 51 | `directory_compare` | Tree comparison | Compare two directories without copying. |
| 52 | `backup_manifest` | Integrity manifests | Create a JSON list of file hashes. |
| 53 | `log_sampler` | Unified logs | Read a bounded slice of recent logs. |
| 54 | `spotlight_search` | Local search indexes | Query Spotlight and restrict it to a path. |

Each entry is both a Python module under `mac_tinker/tools/` and a wrapper under `tools/`, so it is independently runnable.

## A second afternoon of niche experiments

The first 42 tools are mostly observability instruments. The next 12 are deliberately playful: they expose a new programming idea in a form that produces an immediate, visible result.

| Niche skill | Try this | What to notice |
|---|---|---|
| macOS app automation | `python3 tools/open_in_app.py https://docs.python.org --app Safari` | Python builds an argument list and hands it to macOS. |
| speech interfaces | `python3 tools/speak_text.py "Python is a tiny robot assistant"` | A string can become an OS-level action. |
| text encoding | `python3 tools/unicode_inspector.py "café ☕"` | One visible character may have multiple normalized byte representations. |
| web encoding | `python3 tools/url_encode_lab.py --encode "café & tea"` | Spaces and punctuation need a transport-safe representation. |
| binary data | `python3 tools/bytes_viewer.py README.md --bytes 64` | Text files are still bytes underneath. |
| backup engineering | `python3 tools/backup_manifest.py ~/Documents --output manifest.json` | A manifest is a shopping list plus a tamper-evident fingerprint. |
| local search | `python3 tools/spotlight_search.py 'kMDItemFSName == *.pdf' --path ~/Documents` | A search query can be treated as a small language. |
| logs and evidence | `python3 tools/log_sampler.py --last 5m` | A log is a time-ordered diary of system events. |
| visual composition | `python3 tools/image_contact_sheet.py ~/Pictures --output sheet.jpg` | A loop can turn many files into one visual index. |
| comparison | `python3 tools/directory_compare.py ./old ./new` | “Different” can mean missing, extra, or changed. |

Apple’s automation guide describes scripting as a way to automate repetitive tasks by interacting with apps, processes, and the operating system.[7] These experiments stay deliberately small: `open_in_app`, `speak_text`, and `clipboard_put` are explicit actions, while inspection tools remain passive. Automator is useful for simple linear workflows; Python becomes interesting when you add branching, validation, or data transformation.[7]

For a beginner-friendly progression, start with `calendar_month`, `unicode_inspector`, and `url_encode_lab`. Then try `base64_lab`, `bytes_viewer`, and `directory_compare`. Finish with `backup_manifest`, where you can learn file traversal, hashing, JSON serialization, and error handling in one compact project.

## A first afternoon of experiments

### 1. Establish a baseline

Run `system_snapshot.py`, `storage_overview.py`, and `python_env_report.py`. Save JSON reports with shell redirection:

```bash
mkdir -p ~/Desktop/tinker-reports
python3 tools/system_snapshot.py --json > ~/Desktop/tinker-reports/system.json
python3 tools/storage_overview.py --json > ~/Desktop/tinker-reports/storage.json
python3 tools/python_env_report.py --json > ~/Desktop/tinker-reports/python.json
```

Think of these reports as “before” photographs. After installing a package, opening a large project, or connecting to another network, run them again and compare.

### 2. Explore the filesystem without touching it

```bash
python3 tools/folder_tree.py ~/Documents --depth 2
python3 tools/large_files.py ~/Downloads --count 15
python3 tools/file_age_report.py ~/Downloads --days 14
python3 tools/duplicate_finder ~/Pictures --min-size 500K
```

The important lesson is that **finding a candidate is not the same as deciding to delete it**. A duplicate finder is a detective, not a garbage collector.

### 3. Watch a controlled experiment

Create a temporary folder and watch it in one Terminal window:

```bash
mkdir -p /tmp/tinker-watch
python3 tools/file_watch.py /tmp/tinker-watch --seconds 20 --interval 1
```

While it is watching, create and edit a file in another window. The tool is implementing a simple polling loop: take a snapshot, wait, take another, compare.

### 4. Learn networking with a server you control

Start a local server in one window:

```bash
python3 -m http.server 8765 --directory /tmp/tinker-watch
```

Then, in another:

```bash
python3 tools/port_check.py 127.0.0.1 8765
python3 tools/url_headers.py http://127.0.0.1:8765/
```

This is a safe network lab because it targets your own computer. Avoid scanning networks or ports that you do not own or have permission to test.

### 5. Understand fingerprints

```bash
python3 tools/hash_lab.py --file README.md
python3 tools/hash_lab.py --text "same words, same fingerprint"
```

A cryptographic hash is like a document’s tamper-evident wax seal. It does not tell you the whole document, but a changed document should normally produce a different seal.

## Deeper dives

### Why the wrappers exist

The importable implementation lives in `mac_tinker.tools`. The wrapper adjusts `sys.path` to the repository root and calls that module’s `main()` function. This makes each tool easy to run while keeping shared behavior in one place. It also lets a curious learner open either the tiny wrapper or the fuller implementation.

### Why `subprocess` is used carefully

macOS exposes many useful observations through built-in commands. Python’s `subprocess.run()` is used with argument lists instead of shell command strings, bounded timeouts, captured output, and no shell interpolation. This is the programming equivalent of handing a technician a labeled tool instead of letting an untrusted note control the entire workshop.

### Why plist files matter

Apple uses property-list files for structured configuration. Python’s `plistlib` lets the tools parse those files into dictionaries and lists instead of scraping text. The launchd linter checks for common keys but does **not** load a job. Apple’s documentation describes `Label` as the identifier and `ProgramArguments` as the launch command data.[1]

Apple’s Terminal User Guide explains that `launchd` manages daemons and agents and that `launchctl` is the user-facing command for managing them.[2] The tool therefore inventories and validates launch-agent files but does not call `launchctl load`, `bootout`, or other state-changing operations.

### Why duplicate detection hashes in two stages

The duplicate finder first groups files by byte size. Two byte-for-byte equal files must have equal size, so this avoids hashing every unrelated file. It then computes SHA-256 only for same-size candidates. A hash match is strong evidence of identical bytes, but the tool still reports paths rather than deleting one; the human remains responsible for understanding hard links, backups, permissions, and application-managed files.

### Why time-series tools are intentionally simple

`disk_space_watch.py` and `file_watch.py` use polling. Polling is like looking at a clock every minute. It is easy to understand and portable, but it can miss changes that happen between samples. A more advanced version could use macOS-specific filesystem event APIs, but the simple version is a better first lesson because its data model is visible in a few lines.

### JSON as a bridge to bigger projects

A tool that emits JSON can become a component in a larger workflow. For example:

```bash
python3 tools/large_files.py ~/Downloads --json > large.json
python3 -c 'import json; d=json.load(open("large.json")); print(d[0]["path"])'
```

The command-line tool is the “sensor,” JSON is the labeled parcel, and a later script can be the “control room.” This separation makes experiments composable without requiring a full web app.

## How to extend the toolkit

A good personal extension follows the same four-part shape: parse input, do one transformation, emit a readable result, and optionally emit JSON. Copy `calendar_month.py` into a new file and add one small feature, such as a `--week-start` option. Then run a syntax check and a help check:

```bash
python3 -m py_compile mac_tinker/tools/your_new_tool.py
python3 tools/your_new_tool.py --help
```

The Python standard library is a particularly good playground for this repository because it includes modules for paths, regular expressions, dates, Unicode, hashes, subprocesses, SQLite, and URL handling.[3] The intent is not to hide these modules behind a framework; it is to make their inputs and outputs easy to observe.

## Guardrails and privacy

Do not paste clipboard output, EXIF metadata, filenames, or system reports into a public issue without reviewing them. File names and metadata can reveal people, locations, project names, or account identifiers. Keep reports local unless you intentionally redact them.

The tools do not promise that every command works on every macOS release. Apple changes private command details and permissions over time. If a command returns an error, read the captured `stderr`, run the tool with `--help`, and check the relevant Apple documentation. Do not “fix” an error by adding `sudo` unless you understand exactly why elevated access is necessary.

## References

[1]: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html "Apple Developer: Creating Launch Daemons and Agents"
[2]: https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac "Apple Support: Script management with launchd in Terminal on Mac"
[3]: https://docs.python.org/3/library/index.html "Python Standard Library documentation"
[4]: https://docs.python.org/3/library/plistlib.html "Python plistlib documentation"
[5]: https://docs.python.org/3/library/subprocess.html "Python subprocess documentation"
[6]: https://docs.python.org/3/library/sqlite3.html "Python sqlite3 documentation"
[7]: https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/index.html "Apple Developer: Mac Automation Scripting Guide"
