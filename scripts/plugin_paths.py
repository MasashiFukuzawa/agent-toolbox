"""Filesystem boundary checks for repository and plugin content readers."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Set
from functools import lru_cache
from pathlib import Path

from pathspec.gitignore import GitIgnoreSpec


def repository_boundary_errors(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()
    try:
        ignored_files, ignored_dirs = git_ignored_entries(root)
    except ValueError as exc:
        return [str(exc)]

    def ignored(path: Path) -> bool:
        try:
            return is_ignored_path(root, path, ignored_files, ignored_dirs)
        except ValueError as exc:
            errors.append(f"cannot determine ignore status for {path.relative_to(root)}: {exc}")
            return True

    def onerror(exc: OSError) -> None:
        errors.append(f"cannot inspect repository paths: {exc}")

    for directory, child_dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        child_dirs[:] = [
            name
            for name in child_dirs
            if not (Path(directory) == root and name == "plugins")
            and not (Path(directory) == root and _is_local_root_directory_ignored(root, name))
            and not ignored(Path(directory) / name)
        ]
        for name in (*child_dirs, *files):
            path = Path(directory) / name
            if ignored(path):
                continue
            if not path.is_symlink():
                continue
            target = path_within_root(root, path)
            if target is None:
                errors.append(f"repository path escapes root or is unresolved: {path.relative_to(root)}")
            elif ignored(target):
                errors.append(f"repository symlink targets ignored content: {path.relative_to(root)}")
            elif path.is_dir():
                errors.append(f"repository directory symlinks are not allowed: {path.relative_to(root)}")
    return errors


def plugin_boundary_errors(root: Path) -> list[str]:
    root = root.resolve()
    plugins_root = root / "plugins"
    if plugins_root.is_symlink():
        return ["plugins directory escapes repository through a symlink"]
    if not plugins_root.is_dir():
        return ["plugins directory is missing"]

    errors: list[str] = []
    try:
        ignored_files, ignored_dirs = git_ignored_entries(root)
    except ValueError as exc:
        return [str(exc)]

    def ignored(path: Path) -> bool:
        try:
            return is_ignored_path(root, path, ignored_files, ignored_dirs)
        except ValueError as exc:
            errors.append(f"cannot determine ignore status for {path.relative_to(root)}: {exc}")
            return True

    for plugin_dir in plugins_root.iterdir():
        if ignored(plugin_dir):
            continue
        if plugin_dir.is_symlink():
            errors.append(f"plugin entry must not be a symlink: {plugin_dir.relative_to(root)}")
            continue
        if not plugin_dir.is_dir():
            continue
        def onerror(exc: OSError, current_plugin: Path = plugin_dir) -> None:
            errors.append(f"cannot inspect plugin paths under {current_plugin.relative_to(root)}: {exc}")

        for directory, child_dirs, files in os.walk(plugin_dir, followlinks=False, onerror=onerror):
            child_dirs[:] = [
                name
                for name in child_dirs
                if not ignored(Path(directory) / name)
            ]
            for name in (*child_dirs, *files):
                path = Path(directory) / name
                if ignored(path):
                    continue
                if not path.is_symlink():
                    continue
                target = plugin_path_within(root, plugin_dir, path)
                if target is None:
                    errors.append(f"plugin path escapes plugin: {path.relative_to(root)}")
                elif ignored(target):
                    errors.append(f"plugin symlink targets ignored content: {path.relative_to(root)}")
                elif path.is_dir():
                    errors.append(f"plugin directory symlinks are not allowed: {path.relative_to(root)}")
    return errors


def require_safe_repository_paths(root: Path) -> None:
    errors = repository_boundary_errors(root) + plugin_boundary_errors(root)
    if errors:
        raise ValueError("unsafe repository paths:\n" + "\n".join(errors))


def plugin_path_within(root: Path, plugin_dir: Path, path: Path) -> Path | None:
    if plugin_dir.is_symlink() or (root / "plugins").is_symlink():
        return None
    return path_within_root(plugin_dir, path)


def path_within_root(root: Path, path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


@lru_cache(maxsize=8)
def git_ignored_entries(root: Path) -> tuple[frozenset[Path], frozenset[Path]]:
    """Return untracked paths ignored by repository .gitignore files."""
    root = root.resolve()
    try:
        top_level = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, check=False, text=True
        )
    except OSError as exc:
        if os.path.lexists(root / ".git"):
            raise ValueError(f"cannot determine Git-ignored paths under {root}: git is unavailable") from exc
        return frozenset(), frozenset()
    if top_level.returncode or Path(top_level.stdout.strip()).resolve() != root:
        if os.path.lexists(root / ".git"):
            raise ValueError(f"cannot determine Git-ignored paths under {root}: git rev-parse failed")
        return frozenset(), frozenset()
    _reject_symlink_gitignore_files(root)
    try:
        untracked_result = subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-per-directory=.gitignore",
                "--directory",
                "-z",
            ],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"cannot determine Git-ignored paths under {root}: {exc}") from exc
    if untracked_result.returncode:
        raise ValueError(f"cannot determine Git-ignored paths under {root}: git ls-files failed")
    files: set[Path] = set()
    directories: set[Path] = set()
    for raw in untracked_result.stdout.split(b"\0"):
        if not raw:
            continue
        is_directory = raw.endswith(b"/")
        relative = Path(os.fsdecode(raw.rstrip(b"/")))
        (directories if is_directory else files).add(relative)
    return frozenset(files), frozenset(directories)


def _reject_symlink_gitignore_files(root: Path) -> None:
    """Fail closed before Git can follow a symlink while loading ignore rules."""

    def onerror(exc: OSError) -> None:
        raise ValueError(f"cannot inspect ignore rules under {root}: {exc}") from exc

    for directory_name, child_dirs, _files in os.walk(root, followlinks=False, onerror=onerror):
        directory = Path(directory_name)
        ignore_file = directory / ".gitignore"
        if ignore_file.is_symlink():
            raise ValueError(f"ignore rules file is a symlink: {ignore_file}")
        child_dirs[:] = [
            name
            for name in child_dirs
            if name != ".git"
            and not (directory / name).is_symlink()
            and not (directory == root and _is_local_root_directory_ignored(root, name))
            and (
                _git_path_is_tracked(root, (directory / name).relative_to(root))
                or not _fallback_ignored_path(root, (directory / name).relative_to(root))
            )
        ]


@lru_cache(maxsize=8)
def _is_git_root(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, check=False, text=True
        )
    except OSError:
        return False
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == root.resolve()


def is_tracked_file(root: Path, path: Path) -> bool | None:
    """Return whether a file is tracked, or None when the root has no Git index."""
    root_argument = Path(os.path.abspath(root))
    root = root_argument.resolve()
    if not _is_git_root(root):
        if os.path.lexists(root / ".git"):
            raise ValueError(f"cannot verify Git tracking status under {root}")
        return None
    rooted_path = _path_within_root_lexically(root_argument, root, path)
    if rooted_path is None:
        raise ValueError(f"repository input escapes root: {path}")
    relative = rooted_path.relative_to(root)
    if ".." in relative.parts:
        raise ValueError(f"repository input contains parent traversal: {path}")
    return _git_path_is_tracked(root, relative)


@lru_cache(maxsize=256)
def _git_path_is_tracked(root: Path, relative: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "--literal-pathspecs", "ls-files", "--error-unmatch", "--", relative.as_posix()],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"cannot check Git tracking status for {relative} under {root}: {exc}") from exc
    if result.returncode not in {0, 1}:
        raise ValueError(f"cannot check Git tracking status for {relative} under {root}: git ls-files failed")
    return result.returncode == 0


@lru_cache(maxsize=256)
def _git_check_ignored(root: Path, relative: Path) -> bool:
    if _git_path_is_tracked(root, relative):
        return False
    return _fallback_ignored_path(root, relative)


_LOCAL_ROOT_DIRECTORIES = {
    ".git",
    ".venv",
    ".claude",
    ".codex",
    ".playwright-cli",
    ".playwright-mcp",
}


def _is_local_root_directory_ignored(root: Path, name: str) -> bool:
    if name not in _LOCAL_ROOT_DIRECTORIES:
        return False
    if name == ".git" or not _is_git_root(root):
        return True
    return not _git_path_is_tracked(root, Path(name))


def is_ignored_path(
    root: Path, path: Path, ignored_files: Set[Path], ignored_dirs: Set[Path]
) -> bool:
    root_argument = Path(os.path.abspath(root))
    root = root_argument.resolve()
    normalized_path = _path_within_root_lexically(root_argument, root, path, resolve_alias=True)
    if normalized_path is None:
        return False
    relative = normalized_path.relative_to(root)
    if ".git" in relative.parts:
        return True
    if relative.parts and relative.parts[0] in _LOCAL_ROOT_DIRECTORIES:
        if _is_local_root_directory_ignored(root, relative.parts[0]):
            return True
        if not _git_path_is_tracked(root, relative):
            return True
    ignored_paths = ignored_files | ignored_dirs
    if any(ignored_path == relative or ignored_path in relative.parents for ignored_path in ignored_paths):
        return True
    if _is_git_root(root):
        # `git ls-files --others --ignored --directory` can omit an ignored
        # directory symlink. Check symlink ancestors directly so descendants
        # cannot be discovered through such a path.
        for candidate in (relative, *relative.parents):
            if candidate == Path("."):
                break
            if (root / candidate).is_symlink() and _git_check_ignored(root, candidate):
                return True
        return False
    return _fallback_ignored_path(root, relative)


def _fallback_ignored_path(root: Path, relative: Path) -> bool:
    """Apply .gitignore rules and local-state exclusions without a Git worktree."""
    parts = relative.parts
    if not parts:
        return False
    if ".git" in parts:
        return True
    if parts[0] in _LOCAL_ROOT_DIRECTORIES:
        return True

    target = root / relative
    target_is_dir = target.is_dir() and not target.is_symlink()
    last_directory_depth = len(parts) if target_is_dir else len(parts) - 1
    ignored_directories: dict[int, bool] = {}
    ignored = False
    for depth in range(len(parts)):
        if ignored_directories.get(depth, False):
            continue
        directory = root.joinpath(*parts[:depth]) if depth else root
        # Do not follow a path symlink while loading ignore rules. Required
        # file callers perform the final boundary check after this function,
        # but reading a linked directory's .gitignore would already cross it.
        if directory != root and directory.is_symlink():
            break
        ignore_file = directory / ".gitignore"
        spec = _fallback_gitignore_spec(ignore_file)
        if spec is None:
            continue
        candidate = Path(*parts[depth:]).as_posix()
        result = spec.check_file(candidate)
        if result.include is not None:
            ignored = result.include
        if target_is_dir:
            directory_result = spec.check_file(candidate.rstrip("/") + "/")
            if directory_result.include is not None:
                ignored = directory_result.include
        for directory_depth in range(depth + 1, last_directory_depth + 1):
            directory_candidate = Path(*parts[depth:directory_depth]).as_posix() + "/"
            directory_result = spec.check_file(directory_candidate)
            if directory_result.include is not None:
                ignored_directories[directory_depth] = directory_result.include
    return ignored or any(ignored_directories.values())


@lru_cache(maxsize=256)
def _fallback_gitignore_spec(path: Path) -> GitIgnoreSpec | None:
    if path.is_symlink():
        raise ValueError(f"ignore rules file is a symlink: {path}")
    try:
        return GitIgnoreSpec.from_lines(path.read_text(encoding="utf-8").splitlines())
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read ignore rules from {path}: {exc}") from exc


def public_paths(root: Path, paths: list[Path]) -> list[Path]:
    root = root.resolve()
    ignored_files, ignored_dirs = git_ignored_entries(root)
    return [
        path
        for path in paths
        if not is_ignored_content_path(root, path, ignored_files, ignored_dirs)
    ]


def iter_public_files(root: Path, suffix: str | None = None):
    """Yield distributable files without following directory symlinks or entering ignored state."""
    root = root.resolve()
    ignored_files, ignored_dirs = git_ignored_entries(root)
    for directory, child_dirs, files in os.walk(root, followlinks=False):
        child_dirs[:] = [
            name
            for name in child_dirs
            if not (Path(directory) == root and _is_local_root_directory_ignored(root, name))
            and not is_ignored_path(root, Path(directory) / name, ignored_files, ignored_dirs)
        ]
        for name in files:
            path = Path(directory) / name
            if is_ignored_content_path(root, path, ignored_files, ignored_dirs):
                continue
            if suffix is None or path.name.endswith(suffix):
                yield path


def require_public_file(root: Path, path: Path) -> Path:
    """Resolve a required input only when it is public and stays inside the repository."""
    root_argument = Path(os.path.abspath(root))
    root = root_argument.resolve()
    relative = _path_within_root_lexically(root_argument, root, path)
    if relative is None:
        raise ValueError(f"required repository input escapes root: {path}")
    relative = relative.relative_to(root)
    if ".." in relative.parts:
        raise ValueError(f"required repository input contains parent traversal: {path}")
    path = root / relative
    ignored_files, ignored_dirs = git_ignored_entries(root)
    if is_ignored_content_path(root, path, ignored_files, ignored_dirs):
        raise ValueError(f"required repository input is ignored: {path}")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"required repository input is missing or unresolved: {path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"required repository input escapes root: {path}") from exc
    parent = path.parent
    while parent != root.parent:
        if parent.is_symlink():
            raise ValueError(f"required repository input traverses a symlink directory: {path}")
        parent = parent.parent
    if not resolved.is_file():
        raise ValueError(f"required repository input is not a file: {path}")
    return resolved


def is_ignored_content_path(
    root: Path, path: Path, ignored_files: Set[Path], ignored_dirs: Set[Path]
) -> bool:
    root_argument = Path(os.path.abspath(root))
    root = root_argument.resolve()
    normalized_path = _path_within_root_lexically(root_argument, root, path, resolve_alias=True)
    if normalized_path is None:
        return False
    if is_ignored_path(root, normalized_path, ignored_files, ignored_dirs):
        return True
    if not path.is_symlink():
        return False
    try:
        target = path.resolve(strict=True)
        target.relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return is_ignored_path(root, target, ignored_files, ignored_dirs)


def _path_within_root_lexically(
    root_argument: Path, root: Path, path: Path, *, resolve_alias: bool = False
) -> Path | None:
    """Rebase paths from either lexical or resolved root spelling onto the resolved root."""
    if not path.is_absolute():
        return root / path
    for candidate_root in (root_argument, root):
        try:
            return root / path.relative_to(candidate_root)
        except ValueError:
            continue
    if resolve_alias:
        try:
            relative = path.resolve(strict=False).relative_to(root)
            return root / relative
        except (OSError, RuntimeError, ValueError):
            return None
    return None
