"""Build the distributable skills-only plugin ZIP from an explicit list of public files."""

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
FILES = (
    "plugin.json",
    "assets/channel-review.png",
    "skills/review-video-contribution/SKILL.md",
    "skills/review-video-contribution/agents/openai.yaml",
    "skills/review-video-contribution/references/worked-case.md",
    ".claude-plugin/plugin.json",
    "LICENSE",
)


def build(output: Path) -> None:
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    listing = manifest["extensions"]["com.openai"]["interface"]
    for field, limit in {"displayName": 30, "shortDescription": 30, "longDescription": 4000}.items():
        assert 0 < len(listing[field]) <= limit, f"{field} exceeds its listing limit"
    assert all(len(prompt) <= 128 for prompt in listing["defaultPrompt"])
    assert len(listing["defaultPrompt"]) <= 3
    for field in ("logo", "composerIcon"):
        assert listing[field].removeprefix("./") in FILES

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w") as archive:
        for name in sorted(FILES):
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            source = ROOT.parents[1] / "LICENSE" if name == "LICENSE" else ROOT / name
            archive.writestr(entry, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
