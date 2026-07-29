import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from git import Repo, GitCommandError

from app.core.config import settings
from app.core.exceptions import InvalidRepositoryUrlException, RepositoryCloneException

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepositoryMetadata:
    repository_name: str
    repository_url: str
    local_path: str
    default_branch: str | None
    latest_commit: str | None
    total_files: int
    total_directories: int
    top_level_items: list[str]
    important_files: list[str]


class RepositoryAnalysisAgent:
    GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$")
    IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "target", "__pycache__"}

    def validate_github_url(self, github_url: str) -> None:
        clean_url = github_url.strip().removesuffix(".git")
        if not self.GITHUB_URL_PATTERN.match(clean_url):
            raise InvalidRepositoryUrlException("Invalid GitHub repository URL. Use https://github.com/owner/repo")

    def clone_repository(self, github_url: str) -> Path:
        self.validate_github_url(github_url)
        settings.workspace_path.mkdir(parents=True, exist_ok=True)

        repo_name = self._extract_repo_name(github_url)
        destination = settings.workspace_path / repo_name

        if destination.exists():
            logger.info("Removing existing repository workspace: %s", destination)
            def _remove_readonly(func, path, _):
                import stat, os
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(destination, onerror=_remove_readonly)

        try:
            logger.info("Cloning repository %s into %s", github_url, destination)
            Repo.clone_from(github_url, destination, depth=1)
            return destination
        except GitCommandError as exc:
            logger.exception("Repository clone failed")
            raise RepositoryCloneException(str(exc)) from exc

    def extract_metadata(self, github_url: str, local_path: Path) -> RepositoryMetadata:
        repo = Repo(local_path)
        files, directories, important_files = self.scan_files(local_path)
        top_level_items = sorted([p.name for p in local_path.iterdir() if p.name != ".git"])

        return RepositoryMetadata(
            repository_name=self._extract_repo_name(github_url),
            repository_url=github_url,
            local_path=str(local_path),
            default_branch=self._safe_default_branch(repo),
            latest_commit=repo.head.commit.hexsha if repo.head.is_valid() else None,
            total_files=len(files),
            total_directories=len(directories),
            top_level_items=top_level_items,
            important_files=important_files,
        )

    def scan_files(self, local_path: Path) -> tuple[list[Path], list[Path], list[str]]:
        files: list[Path] = []
        directories: list[Path] = []
        important_files: list[str] = []
        important_names = {
            "package.json", "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle",
            "Dockerfile", "docker-compose.yml", "README.md", "manage.py", "main.py", "app.py"
        }

        for path in local_path.rglob("*"):
            if any(part in self.IGNORED_DIRS for part in path.parts):
                continue
            if path.is_dir():
                directories.append(path)
            elif path.is_file():
                files.append(path)
                if path.name in important_names:
                    important_files.append(str(path.relative_to(local_path)))

        return files, directories, sorted(important_files)

    def _extract_repo_name(self, github_url: str) -> str:
        parsed = urlparse(github_url.strip().removesuffix(".git"))
        return parsed.path.strip("/").split("/")[-1]

    def _safe_default_branch(self, repo: Repo) -> str | None:
        try:
            return repo.active_branch.name
        except Exception:
            return None
