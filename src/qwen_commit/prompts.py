"""Commit-message prompt templates per output style."""

SYSTEM_BASE = (
    "You are a meticulous open-source maintainer writing the commit message "
    "for a staged change.\n"
    "Rules:\n"
    "- Output only the commit message: no code fences, no quotes, no commentary.\n"
    "- Subject line: imperative mood, 72 characters or fewer, no trailing period.\n"
    "- Optional body: explain WHY, wrapped at 80 columns, blank line after subject.\n"
    "- Ground every claim in the diff; never invent files, flags, or numbers.\n"
)

STYLE_SPECS = {
    "conventional": (
        "Style: Conventional Commits. First line is `type(scope): subject` with "
        "type in {feat, fix, docs, refactor, test, chore, perf, build, ci, style}; "
        "scope is the module or file area when obvious; `!` before the colon for "
        "breaking changes."
    ),
    "plain": (
        "Style: plain git convention. A single imperative subject line, plus an "
        "optional body; no type prefixes, no emoji."
    ),
    "emoji": (
        "Style: plain git convention prefixed with exactly one emoji matching the "
        "change kind (✨ feat, 🐛 fix, 📝 docs, ️ refactor, ✅ test, 🔧 chore)."
    ),
}


def build_messages(style: str, diff: str, log: str) -> tuple[str, str]:
    system = SYSTEM_BASE + STYLE_SPECS[style] + "\n"
    user = (
        f"Repository style (recent commits):\n{log or '(new repository)'}\n\n"
        f"Staged diff:\n{diff}\n\n"
        "Write the commit message for this change."
    )
    return system, user
