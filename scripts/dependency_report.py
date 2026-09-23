"""Record installed distributions and declared license/source metadata."""

import importlib.metadata as metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
records = []
direct = {"streamlit", "openai", "python-dotenv"}
for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
    info = dist.metadata
    license_text = info.get("License-Expression") or info.get("License")
    if not license_text:
        license_text = "; ".join(value for value in info.get_all("Classifier", []) if value.startswith("License ::")) or "See package license files"
    records.append({
        "name": info["Name"], "version": dist.version,
        "url": f"https://pypi.org/project/{info['Name']}/{dist.version}/",
        "license": license_text,
        "purpose": "Direct runtime dependency" if info["Name"].lower() in direct else "Transitive dependency or Python packaging tool",
        "requires": dist.requires or [],
    })
target = ROOT / "docs" / "DEPENDENCIES.json"
target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Recorded {len(records)} packages in {target.relative_to(ROOT)}")
