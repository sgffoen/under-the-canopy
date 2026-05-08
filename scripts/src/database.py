from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote
from urllib.request import urlopen, urlretrieve


FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str = ""


def collect_branch_meshes(
    folder_url_or_id: str,
    api_key: str,
    cache_folder: Optional[str] = None,
    download: bool = False,
    branch_count: int = 52,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Collect mesh files from Google Drive branch folders."""
    out_files: List[str] = []
    out_names: List[str] = []
    out_folders: List[str] = []
    log: List[str] = []

    if not download:
        return out_files, out_names, out_folders, ["Download is false; no processing was run."]

    if not folder_url_or_id or not folder_url_or_id.strip():
        return out_files, out_names, out_folders, ["Missing Google Drive folder URL or ID."]

    if not api_key or not api_key.strip():
        return out_files, out_names, out_folders, ["Missing Google Drive API key."]

    root_id = extract_folder_id(folder_url_or_id)
    if not root_id:
        return out_files, out_names, out_folders, ["Could not extract folder ID from input."]

    cache_path: Optional[Path] = None
    if download:
        if not cache_folder or not cache_folder.strip():
            return out_files, out_names, out_folders, ["Download is true, but cacheFolder is empty."]

        cache_path = Path(cache_folder)
        cache_path.mkdir(parents=True, exist_ok=True)

    for index in range(1, branch_count + 1):
        branch_name = f"b-{index:03d}"

        branch_folder = find_child_folder(root_id, branch_name, api_key)
        if branch_folder is None:
            log.append(f"{branch_name}: folder not found.")
            continue

        processed_folder = find_child_folder(branch_folder.id, "processed", api_key)
        if processed_folder is None:
            log.append(f"{branch_name}: processed folder not found.")
            continue

        children = list_children(processed_folder.id, api_key)
        mesh_file = next(
            (
                child
                for child in children
                if child.mime_type != FOLDER_MIME and _is_mesh_name(child.name)
            ),
            None,
        )

        if mesh_file is None:
            log.append(f"{branch_name}: mesh file not found in processed.")
            continue

        download_url = (
            "https://www.googleapis.com/drive/v3/files/"
            f"{mesh_file.id}?alt=media&key={quote(api_key)}"
        )

        extension = Path(mesh_file.name).suffix or ".obj"
        renamed_file_name = f"{branch_name}{extension}"
        result_path = download_url

        if download and cache_path is not None:
            local_path = cache_path / renamed_file_name
            try:
                urlretrieve(download_url, local_path)
            except Exception as exc:
                log.append(f"{branch_name}: download failed - {exc}")
                continue

            result_path = str(local_path)
            log.append(f"{branch_name}: downloaded as {renamed_file_name}")
        else:
            log.append(f"{branch_name}: found {mesh_file.name}")

        out_files.append(result_path)
        out_names.append(renamed_file_name)
        out_folders.append(branch_name)

    return out_files, out_names, out_folders, log


def run_script(
    folder_url_or_id: str = "https://drive.google.com/drive/folders/1aVij9-3XKrhwF79BruJICFT3ty1hwnEE",
    api_key: str= "AIzaSyDBgU8XD-GxJ7nsmUZPg5vd79YEiTul3zw",
    cache_folder: Optional[str] = None,
    download: bool = False,
    branch_count: int = 52,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Compatibility wrapper for Grasshopper-style calling code."""
    return collect_branch_meshes(
        folder_url_or_id=folder_url_or_id,
        api_key=api_key,
        cache_folder=cache_folder,
        download=download,
        branch_count=branch_count,
    )


def format_results_report(
    files: List[str],
    names: List[str],
    folders: List[str],
    report: List[str],
) -> str:
    """Return a human-readable text report for collected branch meshes."""
    lines: List[str] = []

    total = len(files)
    lines.append("Google Drive Summary")
    lines.append("=" * 35)
    lines.append(f"Found files: {total}")
    lines.append("")

    if total:
        folder_width = max(len("Folder"), max(len(folder) for folder in folders))
        name_width = max(len("File Name"), max(len(name) for name in names))

        header = f"{'Folder':<{folder_width}}  {'File Name':<{name_width}}  Path/URL"
        lines.append(header)
        lines.append("-" * len(header))

        for folder, name, path in zip(folders, names, files):
            lines.append(f"{folder:<{folder_width}}  {name:<{name_width}}  {path}")
    else:
        lines.append("No files returned.")

    if report:
        lines.append("")
        lines.append("Log")
        lines.append("-" * 3)
        for item in report:
            lines.append(f"- {item}")

    return "\n".join(lines)


def print_results_report(
    files: List[str],
    names: List[str],
    folders: List[str],
    report: List[str],
) -> str:
    """Print and return the formatted mesh collection report."""
    text = format_results_report(files, names, folders, report)
    print(text)
    return text


def find_child_folder(parent_id: str, folder_name: str, api_key: str) -> Optional[DriveFile]:
    query = (
        f"'{parent_id}' in parents and "
        f"name = '{escape_drive_query(folder_name)}' and "
        f"mimeType = '{FOLDER_MIME}' and "
        "trashed = false"
    )
    result = query_drive(query, api_key)
    return result[0] if result else None


def list_children(parent_id: str, api_key: str) -> List[DriveFile]:
    query = f"'{parent_id}' in parents and trashed = false"
    return query_drive(query, api_key)


def query_drive(query: str, api_key: str) -> List[DriveFile]:
    files: List[DriveFile] = []
    page_token: Optional[str] = None

    while True:
        url = (
            "https://www.googleapis.com/drive/v3/files"
            f"?q={quote(query)}"
            f"&fields={quote('files(id,name,mimeType),nextPageToken')}"
            "&pageSize=100"
            "&supportsAllDrives=true"
            "&includeItemsFromAllDrives=true"
            f"&key={quote(api_key)}"
        )

        if page_token:
            url += f"&pageToken={quote(page_token)}"

        with urlopen(url) as response:
            payload = json.load(response)

        files.extend(parse_files(payload))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return files


def parse_files(payload: dict) -> List[DriveFile]:
    result: List[DriveFile] = []
    for item in payload.get("files", []):
        file_id = item.get("id")
        name = item.get("name")
        if not file_id or not name:
            continue

        result.append(
            DriveFile(
                id=file_id,
                name=name,
                mime_type=item.get("mimeType", ""),
            )
        )
    return result


def extract_folder_id(value: str) -> Optional[str]:
    value = value.strip()

    if "/" not in value and "?" not in value:
        return value

    folder_match = re.search(r"/folders/([^/?&]+)", value)
    if folder_match:
        return folder_match.group(1)

    id_match = re.search(r"[?&]id=([^&]+)", value)
    if id_match:
        return id_match.group(1)

    return None


def escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _is_mesh_name(name: str) -> bool:
    stem = Path(name).stem
    return stem.lower() == "mesh" or name.lower() == "mesh"