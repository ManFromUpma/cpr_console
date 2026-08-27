# MacBook tinkering research notes

## Apple launchd sources

Apple's Terminal User Guide says that `launchd` manages macOS daemons and agents, and users interact with it through `launchctl` rather than directly. It identifies these locations: `/System/Library/LaunchDaemons` (Apple system daemons), `/System/Library/LaunchAgents` (Apple per-user agents), `/Library/LaunchDaemons` (third-party system daemons), `/Library/LaunchAgents` (third-party agents for all users), and `~/Library/LaunchAgents` (third-party agents for the logged-in user).

Apple's Developer documentation explains that a launchd job is configured with a property-list file. A `Label` uniquely identifies the job and `ProgramArguments` describes how it is launched; `KeepAlive` is optional and controls whether the job is kept running. The same plist structure is used for daemons and agents, with the directory determining which kind it is.

Sources:
- https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac
- https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html

Implementation decision: include read-only launchd inventory and plist inspection tools, plus a generator that writes a user-level plist only when explicitly asked. Avoid loading/unloading jobs automatically.

## Tool design principles

Build standalone, standard-library-first scripts that are safe by default. Read-only tools may inspect local metadata, files, processes, logs, network state, disks, and power state. Any operation that can modify files should default to preview/dry-run and require an explicit `--apply` flag. Each tool should support `--json` where practical, return a non-zero code for invalid input, and work on non-macOS systems with a clear capability message when feasible.

Proposed coverage: system orientation, storage hygiene, file metadata and duplicates, developer-workspace health, launchd and plist tinkering, network diagnostics, power and battery observation, screenshots/clipboard/Quick Look helpers, and privacy-oriented local inspection.

## Second-wave niche research

Apple's Mac Automation Scripting Guide frames scripting as a way to automate repetitive tasks by having scripts interact with apps, processes, and the operating system. It points to AppleScript and JavaScript for Automation as primary macOS automation languages, while also noting Python and Perl as scripting languages. It distinguishes simple linear Automator workflows from more complex branching scripts and lists approachable topics such as files and folders, text and numbers, notifications, speaking text, URLs, plist files, watching folders, and calling command-line tools.

The Python Standard Library documentation confirms that many of these learning projects can be built without third-party dependencies. Relevant modules include `re` for regular expressions, `difflib` for deltas, `unicodedata` for Unicode inspection, `calendar` and `datetime` for time, `pathlib` for filesystem paths, `filecmp` for comparison, `hashlib` for hashes, `sqlite3` for SQLite databases, and `subprocess` for invoking system tools.

Second-wave niche areas selected: data-shaping and validation, text and Unicode forensics, local database exploration, image composition and metadata, and polling-based filesystem observation. These are approachable because each has a visible input, a small transformation, and a tangible output.

Sources:
- https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/index.html
- https://docs.python.org/3/library/index.html
