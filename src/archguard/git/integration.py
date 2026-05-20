"""Git integration for ArchGuard."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from git import Repo  # type: ignore[attr-defined]
from git.exc import InvalidGitRepositoryError
from git.objects.commit import Commit

from archguard.types import PathLike, ProjectSnapshot, TrendAnalysis

logger = logging.getLogger(__name__)


@dataclass
class PRDiff:
    """Represents a PR diff."""

    files_added: list[Path] = field(default_factory=list)
    files_modified: list[Path] = field(default_factory=list)
    files_deleted: list[Path] = field(default_factory=list)
    base_commit: str = ""
    head_commit: str = ""

    @property
    def all_files(self) -> list[Path]:
        """Get all affected files."""
        return self.files_added + self.files_modified

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "files_added": [str(f) for f in self.files_added],
            "files_modified": [str(f) for f in self.files_modified],
            "files_deleted": [str(f) for f in self.files_deleted],
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "total_files": len(self.all_files),
        }


class GitIntegration:
    """Integration with Git repositories."""

    def __init__(self, repo_path: PathLike | None = None) -> None:
        """Initialize Git integration.
        
        Args:
            repo_path: Path to Git repository. If None, uses current directory.
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.repo: Repo | None = None

        try:
            self.repo = Repo(self.repo_path, search_parent_directories=True)
            assert self.repo is not None
            working_dir = self.repo.working_dir
            logger.info(f"Initialized Git integration for {working_dir or self.repo_path}")
        except InvalidGitRepositoryError:
            logger.warning(f"No Git repository found at {self.repo_path}")

    def is_valid(self) -> bool:
        """Check if Git integration is valid."""
        return self.repo is not None and not self.repo.bare

    def get_current_commit(self) -> str:
        """Get current commit hash."""
        if not self.is_valid():
            return "unknown"
        return self.repo.head.commit.hexsha[:12]  # type: ignore

    def get_current_branch(self) -> str:
        """Get current branch name."""
        if not self.is_valid():
            return "unknown"
        try:
            return self.repo.active_branch.name  # type: ignore
        except Exception:
            return "detached"

    def get_pr_diff(
        self,
        base_branch: str = "main",
        head: str | None = None
    ) -> PRDiff:
        """Get diff between current branch and base branch.
        
        Args:
            base_branch: Base branch to compare against.
            head: Head commit/branch. If None, uses current HEAD.
            
        Returns:
            PRDiff with changed files.
        """
        if not self.is_valid():
            return PRDiff()

        diff = PRDiff()

        try:
            # Get commits
            base_commit = self.repo.commit(base_branch)  # type: ignore
            head_commit = self.repo.commit(head) if head else self.repo.head.commit  # type: ignore

            diff.base_commit = base_commit.hexsha[:12]
            diff.head_commit = head_commit.hexsha[:12]

            # Get diff
            git_diff = head_commit.diff(base_commit)

            for item in git_diff:
                file_path = Path(item.a_path) if item.a_path else Path(item.b_path)

                # Only include Python files
                if file_path.suffix != ".py":
                    continue

                if item.new_file:
                    diff.files_added.append(file_path)
                elif item.deleted_file:
                    diff.files_deleted.append(file_path)
                else:
                    diff.files_modified.append(file_path)

        except Exception as e:
            logger.error(f"Error getting PR diff: {e}")

        return diff

    def get_changed_files_since(
        self,
        since_commit: str,
        include_untracked: bool = False
    ) -> list[Path]:
        """Get files changed since a specific commit.
        
        Args:
            since_commit: Commit hash to compare against.
            include_untracked: Whether to include untracked files.
            
        Returns:
            List of changed file paths.
        """
        if not self.is_valid():
            return []

        changed_files: set[str] = set()

        try:
            # Get diff against commit
            diff = self.repo.head.commit.diff(since_commit)  # type: ignore

            for item in diff:
                if item.a_path:
                    changed_files.add(item.a_path)
                if item.b_path:
                    changed_files.add(item.b_path)

            # Include untracked files if requested
            if include_untracked:
                untracked = self.repo.untracked_files  # type: ignore
                changed_files.update(untracked)

        except Exception as e:
            logger.error(f"Error getting changed files: {e}")

        # Filter to Python files only
        return [
            Path(f) for f in changed_files
            if f.endswith(".py")
        ]

    def get_commit_history(
        self,
        max_commits: int = 10,
        branch: str | None = None
    ) -> list[Commit]:
        """Get commit history.
        
        Args:
            max_commits: Maximum number of commits to retrieve.
            branch: Branch to get history from. If None, uses current.
            
        Returns:
            List of commits.
        """
        if not self.is_valid():
            return []

        try:
            if branch:
                ref = self.repo.commit(branch)  # type: ignore
            else:
                ref = self.repo.head.commit  # type: ignore

            commits = []
            for commit in self.repo.iter_commits(ref, max_count=max_commits):  # type: ignore
                commits.append(commit)

            return commits

        except Exception as e:
            logger.error(f"Error getting commit history: {e}")
            return []

    def get_file_at_commit(
        self,
        file_path: PathLike,
        commit_hash: str
    ) -> str | None:
        """Get file content at a specific commit.
        
        Args:
            file_path: Path to file.
            commit_hash: Commit hash.
            
        Returns:
            File content or None if not found.
        """
        if not self.is_valid():
            return None

        try:
            commit = self.repo.commit(commit_hash)  # type: ignore
            blob = commit.tree / str(file_path)
            return blob.data_stream.read().decode("utf-8")

        except Exception as e:
            logger.warning(f"Could not get file at commit: {e}")
            return None

    def get_project_root(self) -> Path:
        """Get Git repository root."""
        if not self.is_valid():
            return self.repo_path
        return Path(self.repo.working_dir)  # type: ignore


class TrendAnalyzer:
    """Analyzes architecture trends over time."""

    def __init__(self, git_integration: GitIntegration) -> None:
        """Initialize trend analyzer.
        
        Args:
            git_integration: Git integration instance.
        """
        self.git = git_integration

    def analyze_trends(
        self,
        max_commits: int = 10,
        analyzer_callback = None
    ) -> TrendAnalysis:
        """Analyze trends over commit history.
        
        Args:
            max_commits: Number of commits to analyze.
            analyzer_callback: Callback function to analyze a commit.
            
        Returns:
            TrendAnalysis with results.
        """
        trend = TrendAnalysis()

        if not self.git.is_valid():
            logger.warning("Git integration not available for trend analysis")
            return trend

        commits = self.git.get_commit_history(max_commits)

        for commit in commits:
            snapshot = self._analyze_commit(commit, analyzer_callback)
            if snapshot:
                trend.snapshots.append(snapshot)

        # Calculate trend
        trend.calculate_trend()

        return trend

    def _analyze_commit(
        self,
        commit: Commit,
        analyzer_callback
    ) -> ProjectSnapshot | None:
        """Analyze a single commit.
        
        Args:
            commit: Git commit.
            analyzer_callback: Callback to perform analysis.
            
        Returns:
            ProjectSnapshot or None.
        """
        if analyzer_callback is None:
            return None

        try:
            timestamp = datetime.fromtimestamp(commit.committed_date).isoformat()

            # Create snapshot
            snapshot = ProjectSnapshot(
                commit_hash=commit.hexsha[:12],
                timestamp=timestamp,
            )

            # Run analysis (callback should handle git state)
            results = analyzer_callback(commit.hexsha)
            snapshot.results = results

            # Calculate summary
            snapshot.summary = {
                "author": commit.author.name,
                "message": commit.message.splitlines()[0] if commit.message else "",
                "total_files": len(list(commit.stats.files.keys())),
            }

            return snapshot

        except Exception as e:
            logger.error(f"Error analyzing commit {commit.hexsha}: {e}")
            return None

    def calculate_health_delta(
        self,
        base_snapshot: ProjectSnapshot,
        head_snapshot: ProjectSnapshot,
    ) -> dict[str, Any]:
        """Calculate health delta between two snapshots.
        
        Args:
            base_snapshot: Base snapshot.
            head_snapshot: Head snapshot.
            
        Returns:
            Delta information.
        """
        base_violations = base_snapshot.get_total_violations()
        head_violations = head_snapshot.get_total_violations()

        delta = head_violations - base_violations

        # Determine status
        if delta < 0:
            status = "improved"
        elif delta > 0:
            status = "degraded"
        else:
            status = "unchanged"

        # Calculate percentage change
        if base_violations > 0:
            pct_change = (delta / base_violations) * 100
        else:
            pct_change = 0 if head_violations == 0 else 100

        return {
            "status": status,
            "delta": delta,
            "percentage_change": round(pct_change, 2),
            "base_violations": base_violations,
            "head_violations": head_violations,
            "base_commit": base_snapshot.commit_hash,
            "head_commit": head_snapshot.commit_hash,
        }


def get_pr_environment() -> dict[str, Any]:
    """Detect PR environment variables from CI systems.
    
    Returns:
        Dictionary with PR information.
    """
    import os

    # GitHub Actions
    if os.getenv("GITHUB_ACTIONS"):
        return {
            "ci_system": "github_actions",
            "is_pr": os.getenv("GITHUB_EVENT_NAME") == "pull_request",
            "base_branch": os.getenv("GITHUB_BASE_REF", "main"),
            "head_branch": os.getenv("GITHUB_HEAD_REF"),
            "pr_number": os.getenv("GITHUB_REF", "").split("/")[-2] if "/pull/" in os.getenv("GITHUB_REF", "") else None,
            "repo": os.getenv("GITHUB_REPOSITORY"),
            "sha": os.getenv("GITHUB_SHA"),
        }

    # GitLab CI
    if os.getenv("GITLAB_CI"):
        return {
            "ci_system": "gitlab",
            "is_pr": os.getenv("CI_MERGE_REQUEST_ID") is not None,
            "base_branch": os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", os.getenv("CI_DEFAULT_BRANCH", "main")),
            "head_branch": os.getenv("CI_COMMIT_REF_NAME"),
            "pr_number": os.getenv("CI_MERGE_REQUEST_IID"),
            "repo": os.getenv("CI_PROJECT_PATH"),
            "sha": os.getenv("CI_COMMIT_SHA"),
        }

    # CircleCI
    if os.getenv("CIRCLECI"):
        return {
            "ci_system": "circleci",
            "is_pr": os.getenv("CIRCLE_PULL_REQUEST") is not None,
            "base_branch": os.getenv("CIRCLE_BRANCH"),
            "head_branch": os.getenv("CIRCLE_BRANCH"),
            "pr_number": os.getenv("CIRCLE_PR_NUMBER"),
            "repo": f"{os.getenv('CIRCLE_PROJECT_USERNAME')}/{os.getenv('CIRCLE_PROJECT_REPONAME')}",
            "sha": os.getenv("CIRCLE_SHA1"),
        }

    # Default: not in CI
    return {
        "ci_system": None,
        "is_pr": False,
        "base_branch": "main",
        "head_branch": None,
        "pr_number": None,
        "repo": None,
        "sha": None,
    }
