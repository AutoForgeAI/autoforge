from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def find_ui_root(start: Path) -> Path | None:
    """
    Locate the repo-root `ui/` directory (source + build) by walking parents.
    Returns None when running from an installed package without UI sources.
    """
    base = start if start.is_dir() else start.parent
    for parent in [base, *base.parents]:
        ui_dir = parent / "ui"
        if (ui_dir / "package.json").exists():
            return ui_dir
    return None


def _newest_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    if path.is_file():
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
    latest = 0.0
    for entry in path.rglob("*"):
        if not entry.is_file():
            continue
        try:
            latest = max(latest, entry.stat().st_mtime)
        except OSError:
            continue
    return latest


def _newest_mtime_for_paths(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        latest = max(latest, _newest_mtime(path))
    return latest


def _ui_mtime_tolerance_s(ui_root: Path) -> float:
    """
    Mtime tolerance (seconds) for filesystems with coarse timestamp precision.

    Why: some filesystems (FAT32/vfat) only store mtimes with 2s granularity,
    which can cause rebuild loops (source appears "newer" than dist forever).

    Override with `AUTOCODER_UI_MTIME_TOLERANCE_S`.
    """
    raw = str(os.environ.get("AUTOCODER_UI_MTIME_TOLERANCE_S", "")).strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0

    # Default: be strict unless we can confidently detect a coarse FS.
    try:
        if os.name == "nt":
            drive = ui_root.resolve().drive or ""
            if not drive:
                return 0.0

            import ctypes

            fs_name_buf = ctypes.create_unicode_buffer(64)
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                f"{drive}\\",
                None,
                0,
                None,
                None,
                None,
                fs_name_buf,
                len(fs_name_buf),
            )
            if not ok:
                return 0.0
            fs_name = (fs_name_buf.value or "").strip().upper()
            if fs_name in {"FAT32", "FAT", "EXFAT"}:
                return 2.0
            return 0.0

        mounts = Path("/proc/mounts")
        if not mounts.exists():
            return 0.0

        path_str = str(ui_root.resolve())
        best_mount_point = ""
        best_fstype = ""
        for line in mounts.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mount_point = parts[1].replace("\\040", " ")
            fstype = parts[2]
            if path_str.startswith(mount_point) and len(mount_point) > len(best_mount_point):
                best_mount_point = mount_point
                best_fstype = fstype

        if best_fstype.lower() in {"vfat", "msdos", "exfat"}:
            return 2.0
    except Exception:
        return 0.0

    return 0.0


def get_ui_build_stale_trigger(ui_root: Path) -> str | None:
    """
    Return a human-readable trigger for UI rebuilds, or None when up to date.

    This is best-effort and used for debug logging only.
    """
    src_dir = ui_root / "src"
    if not src_dir.exists():
        return None

    dist_dir = ui_root / "dist"
    dist_latest = _newest_mtime(dist_dir)
    if dist_latest <= 0:
        return "ui/dist missing or empty"

    tolerance = _ui_mtime_tolerance_s(ui_root)
    threshold = dist_latest + tolerance

    candidates: list[Path] = [
        src_dir,
        ui_root / "index.html",
        ui_root / "package.json",
        ui_root / "package-lock.json",
        ui_root / "vite.config.ts",
        ui_root / "vite.config.js",
        ui_root / "tailwind.config.ts",
        ui_root / "tailwind.config.js",
        ui_root / "postcss.config.js",
        ui_root / "postcss.config.cjs",
        ui_root / "tsconfig.json",
        ui_root / "tsconfig.app.json",
        ui_root / "tsconfig.node.json",
    ]

    newest_path: Path | None = None
    newest_mtime = 0.0
    for path in candidates:
        if not path.exists():
            continue
        if path.is_dir():
            for entry in path.rglob("*"):
                if not entry.is_file():
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_path = entry
        else:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_path = path

    if newest_mtime <= threshold:
        return None

    if newest_path is None:
        return None

    try:
        return str(newest_path.relative_to(ui_root))
    except Exception:
        return str(newest_path)


def is_ui_build_stale(ui_root: Path) -> bool:
    """
    Return True when `ui/dist` is missing/empty or older than UI source inputs.
    """
    src_dir = ui_root / "src"
    if not src_dir.exists():
        return False

    dist_dir = ui_root / "dist"
    dist_latest = _newest_mtime(dist_dir)
    if dist_latest <= 0:
        return True

    candidates = [
        src_dir,
        ui_root / "index.html",
        ui_root / "package.json",
        ui_root / "vite.config.ts",
        ui_root / "vite.config.js",
        ui_root / "tailwind.config.ts",
        ui_root / "tailwind.config.js",
        ui_root / "postcss.config.js",
        ui_root / "postcss.config.cjs",
        ui_root / "tsconfig.json",
        ui_root / "tsconfig.app.json",
        ui_root / "tsconfig.node.json",
    ]
    source_latest = _newest_mtime_for_paths([p for p in candidates if p.exists()])
    if source_latest <= 0:
        return False

    tolerance = _ui_mtime_tolerance_s(ui_root)
    return source_latest > (dist_latest + tolerance)
