from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_documented_gog_commands_are_structured_and_wrapped() -> None:
    for path in (ROOT / "plugins/gog/skills").glob("*/SKILL.md"):
        commands = [line for line in path.read_text().splitlines() if line.startswith("gog ")]
        assert commands
        for command in commands:
            assert "--json" in command
            assert "--wrap-untrusted" in command
            assert "--no-input" in command
            assert "--force" not in command
