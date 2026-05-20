#!/usr/bin/env python3
"""Install ArchGuard git hooks."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path


def find_git_root(start_path: Path = Path.cwd()) -> Path | None:
    """Find the git repository root."""
    path = start_path.resolve()
    while path.parent != path:
        git_dir = path / ".git"
        if git_dir.exists():
            return path
        path = path.parent
    return None


def install_hooks(
    hooks_dir: Path,
    pre_commit: bool = True,
    pre_push: bool = False,
    force: bool = False,
) -> bool:
    """Install git hooks.
    
    Args:
        hooks_dir: Path to git hooks directory.
        pre_commit: Install pre-commit hook.
        pre_push: Install pre-push hook.
        force: Overwrite existing hooks.
        
    Returns:
        True if successful.
    """
    script_dir = Path(__file__).parent
    success = True
    
    if pre_commit:
        source = script_dir / "pre-commit"
        target = hooks_dir / "pre-commit"
        
        if target.exists() and not force:
            print(f"⚠️  pre-commit hook already exists. Use --force to overwrite.")
        else:
            try:
                shutil.copy2(source, target)
                # Make executable
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                print(f"✅ Installed pre-commit hook: {target}")
            except Exception as e:
                print(f"❌ Failed to install pre-commit hook: {e}")
                success = False
    
    if pre_push:
        source = script_dir / "pre-push"
        target = hooks_dir / "pre-push"
        
        if target.exists() and not force:
            print(f"⚠️  pre-push hook already exists. Use --force to overwrite.")
        else:
            try:
                shutil.copy2(source, target)
                # Make executable
                target.chmod(target.stat().st_mode | stat.S_IEXEC)
                print(f"✅ Installed pre-push hook: {target}")
            except Exception as e:
                print(f"❌ Failed to install pre-push hook: {e}")
                success = False
    
    return success


def uninstall_hooks(hooks_dir: Path) -> bool:
    """Uninstall ArchGuard git hooks.
    
    Args:
        hooks_dir: Path to git hooks directory.
        
    Returns:
        True if successful.
    """
    success = True
    
    for hook_name in ["pre-commit", "pre-push"]:
        target = hooks_dir / hook_name
        
        if target.exists():
            try:
                # Check if it's our hook (contains "ArchGuard")
                content = target.read_text()
                if "ArchGuard" in content:
                    target.unlink()
                    print(f"✅ Removed {hook_name} hook")
                else:
                    print(f"⚠️  {hook_name} hook doesn't appear to be from ArchGuard, skipping")
            except Exception as e:
                print(f"❌ Failed to remove {hook_name} hook: {e}")
                success = False
    
    return success


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install or uninstall ArchGuard git hooks"
    )
    parser.add_argument(
        "--uninstall", "-u",
        action="store_true",
        help="Uninstall hooks instead of installing",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing hooks",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        default=True,
        help="Install pre-commit hook (default: True)",
    )
    parser.add_argument(
        "--pre-push",
        action="store_true",
        help="Install pre-push hook",
    )
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        help="Path to git hooks directory (auto-detected if not specified)",
    )
    
    args = parser.parse_args()
    
    # Find hooks directory
    if args.hooks_dir:
        hooks_dir = args.hooks_dir
    else:
        git_root = find_git_root()
        if not git_root:
            print("❌ Error: Not in a git repository")
            return 1
        hooks_dir = git_root / ".git" / "hooks"
    
    if not hooks_dir.exists():
        print(f"❌ Error: Hooks directory not found: {hooks_dir}")
        return 1
    
    print(f"📁 Git hooks directory: {hooks_dir}")
    
    if args.uninstall:
        print("🗑️  Uninstalling ArchGuard hooks...")
        if uninstall_hooks(hooks_dir):
            print("✅ Hooks uninstalled successfully")
            return 0
        else:
            print("❌ Some hooks could not be uninstalled")
            return 1
    else:
        print("🔧 Installing ArchGuard hooks...")
        if install_hooks(
            hooks_dir,
            pre_commit=args.pre_commit,
            pre_push=args.pre_push,
            force=args.force,
        ):
            print("✅ Hooks installed successfully")
            print("")
            print("To uninstall later, run:")
            print(f"  python {__file__} --uninstall")
            return 0
        else:
            print("❌ Some hooks could not be installed")
            return 1


if __name__ == "__main__":
    sys.exit(main())
