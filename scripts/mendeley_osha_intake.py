"""Collect the CC BY OSHA-derived auxiliary research corpus with provenance.

This is not an ASCENSION SIF or life-saving-rule dataset.  The source labels are
kept as auxiliary construction/industrial safety fields and must not be presented
as validated oil-and-gas SIF results.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request, urlopen


DATASET_PAGE = "https://data.mendeley.com/datasets/8sr95gfttj/1"
DATASET_API = "https://data.mendeley.com/public-api/datasets/8sr95gfttj?version=1"
FILES_API = (
    "https://data.mendeley.com/public-api/datasets/8sr95gfttj/files"
    "?folder_id=0ab07de8-5f39-4465-84e2-0481ea9969ba&version=1"
)
EXPECTED_SOURCE_FILES = {
    "Final_Master_Ensemble_v18_Success_Deidentified.csv",
    "Gemini_Final_Validation_400_Deidentified.csv",
    "OSC_BIM_Risk_Profile.csv",
}
FILES_TO_DOWNLOAD = {
    "Final_Master_Ensemble_v18_Success_Deidentified.csv",
    "Gemini_Final_Validation_400_Deidentified.csv",
}


def fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json, text/csv, */*",
            "User-Agent": "ASCENSION-auxiliary-research-intake/1.0",
        },
    )
    with urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"Source returned HTTP {response.status}: {url}")
        return response.read()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def collect(output: Path) -> None:
    if output.exists():
        raise ValueError(f"Output already exists: {output}")

    metadata_raw = fetch(DATASET_API)
    files_raw = fetch(FILES_API)
    metadata = json.loads(metadata_raw)
    files = json.loads(files_raw)
    if metadata.get("data_licence", {}).get("short_name") != "CC BY 4.0":
        raise ValueError("Expected CC BY 4.0 source licence was not returned")
    sources = {item.get("filename"): item for item in files}
    if set(sources) != EXPECTED_SOURCE_FILES:
        raise ValueError(f"Unexpected source file set: {sorted(sources)}")

    output.mkdir(parents=True)
    source_files = output / "source_files"
    source_files.mkdir()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    source_manifest = []
    for filename in sorted(FILES_TO_DOWNLOAD):
        item = sources[filename]
        download_url = item["content_details"]["download_url"]
        content = fetch(download_url)
        path = source_files / filename
        path.write_bytes(content)
        first_line = content.decode("utf-8-sig").splitlines()[0]
        columns = first_line.split(",")
        source_manifest.append(
            {
                "filename": filename,
                "source_file_id": item["id"],
                "source_download_url": download_url,
                "bytes": len(content),
                "sha256": sha256(content).hexdigest(),
                "column_count": len(columns),
                "columns": columns,
            }
        )

    (output / "source_metadata.json").write_bytes(metadata_raw)
    (output / "source_files_manifest.json").write_bytes(files_raw)
    manifest = {
        "status": "AUXILIARY_RESEARCH_ONLY",
        "source": metadata["name"],
        "doi": metadata["doi"]["id"],
        "dataset_page": DATASET_PAGE,
        "metadata_api": DATASET_API,
        "files_api": FILES_API,
        "licence": metadata["data_licence"],
        "attribution": "Han, H. and Yi, J.-S. (2026), Mendeley Data, DOI: 10.17632/8sr95gfttj.1",
        "retrieved_at": retrieved_at,
        "source_metadata_sha256": sha256(metadata_raw).hexdigest(),
        "source_file_manifest_sha256": sha256(files_raw).hexdigest(),
        "published_files_not_downloaded": sorted(EXPECTED_SOURCE_FILES - FILES_TO_DOWNLOAD),
        "files": source_manifest,
        "synthetic_records": 0,
        "ascension_sif_labels": 0,
        "ascension_life_saving_rule_labels": 0,
        "training_scope": "Auxiliary hazard/evidence extraction research only.",
        "prohibitions": [
            "Do not map source outcomes or construction labels to SIF labels automatically.",
            "Do not use injury outcomes, investigation conclusions or post-event fields as prediction-time inputs.",
            "Do not report oil-and-gas validation results from this source.",
            "Do not enable a live safety decision feature from this auxiliary corpus.",
        ],
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output)
