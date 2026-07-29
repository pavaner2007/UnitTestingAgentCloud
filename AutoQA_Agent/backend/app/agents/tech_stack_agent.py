import json
import logging
from pathlib import Path

from app.schemas.analysis import TechStackResponse

logger = logging.getLogger(__name__)


class TechStackDetectionAgent:
    IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "target", "__pycache__"}

    def detect(self, repo_path: Path) -> TechStackResponse:
        evidence: dict[str, list[str]] = {}
        frontend: set[str] = set()
        backend: set[str] = set()
        languages: set[str] = set()
        databases: set[str] = set()
        frameworks: set[str] = set()
        package_managers: set[str] = set()

        files = self._iter_files(repo_path)
        file_names = {f.name for f in files}
        suffixes = {f.suffix.lower() for f in files}

        if ".py" in suffixes:
            languages.add("Python")
        if ".java" in suffixes:
            languages.add("Java")
        if {".js", ".jsx", ".ts", ".tsx"} & suffixes:
            languages.add("JavaScript/TypeScript")

        if "package.json" in file_names:
            package_managers.add("npm/yarn/pnpm")
            package_json_files = [f for f in files if f.name == "package.json"]
            for package_file in package_json_files:
                data = self._read_json(package_file)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                self._detect_js_stack(deps, frontend, backend, frameworks, evidence, package_file, databases)

        for marker in ["requirements.txt", "pyproject.toml", "Pipfile"]:
            if marker in file_names:
                package_managers.add("pip/poetry/pipenv")
                for f in [x for x in files if x.name == marker]:
                    content = self._safe_read_text(f).lower()
                    self._detect_python_stack(content, backend, frameworks, databases, evidence, f)

        if "pom.xml" in file_names or "build.gradle" in file_names:
            package_managers.add("Maven/Gradle")
            languages.add("Java")
            for f in [x for x in files if x.name in {"pom.xml", "build.gradle"}]:
                content = self._safe_read_text(f).lower()
                if "spring-boot" in content or "springframework.boot" in content:
                    backend.add("Spring Boot")
                    frameworks.add("Spring Boot")
                    evidence.setdefault("Spring Boot", []).append(str(f.relative_to(repo_path)))

        if any(f.name == "manage.py" for f in files):
            backend.add("Django")
            frameworks.add("Django")
            evidence.setdefault("Django", []).append("manage.py")

        if self._contains_text(files, "postgres"):
            databases.add("PostgreSQL")
        if self._contains_text(files, "mongodb") or self._contains_text(files, "mongoose"):
            databases.add("MongoDB")
        if self._contains_text(files, "mysql"):
            databases.add("MySQL")

        return TechStackResponse(
            frontend=sorted(frontend),
            backend=sorted(backend),
            languages=sorted(languages),
            databases=sorted(databases),
            frameworks=sorted(frameworks),
            package_managers=sorted(package_managers),
            raw_evidence=evidence,
        )

    def _detect_js_stack(self, deps, frontend, backend, frameworks, evidence, package_file, databases) -> None:
        checks = {
            "react": (frontend, "React"),
            "next": (frontend, "Next.js"),
            "@angular/core": (frontend, "Angular"),
            "vue": (frontend, "Vue"),
            "express": (backend, "Express.js"),
            "mongoose": (databases, "MongoDB"),
            "pg": (databases, "PostgreSQL"),
            "mysql": (databases, "MySQL"),
            "mysql2": (databases, "MySQL"),
        }
        for dependency, (target, label) in checks.items():
            if dependency in deps:
                target.add(label)
                frameworks.add(label) if label not in {"MongoDB", "PostgreSQL", "MySQL"} else None
                evidence.setdefault(label, []).append(str(package_file))
        if deps:
            backend.add("Node.js")
            evidence.setdefault("Node.js", []).append(str(package_file))

    def _detect_python_stack(self, content, backend, frameworks, databases, evidence, file_path) -> None:
        checks = {
            "fastapi": (backend, "FastAPI"),
            "django": (backend, "Django"),
            "flask": (backend, "Flask"),
            "psycopg2": (databases, "PostgreSQL"),
            "asyncpg": (databases, "PostgreSQL"),
            "pymongo": (databases, "MongoDB"),
            "mysqlclient": (databases, "MySQL"),
        }
        for token, (target, label) in checks.items():
            if token in content:
                target.add(label)
                if label not in {"MongoDB", "PostgreSQL", "MySQL"}:
                    frameworks.add(label)
                evidence.setdefault(label, []).append(str(file_path))

    def _iter_files(self, repo_path: Path) -> list[Path]:
        return [p for p in repo_path.rglob("*") if p.is_file() and not any(part in self.IGNORED_DIRS for part in p.parts)]

    def _read_json(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to parse JSON file: %s", path)
            return {}

    def _safe_read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:200_000]
        except Exception:
            return ""

    def _contains_text(self, files: list[Path], token: str) -> bool:
        token = token.lower()
        searchable_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".env", ".yml", ".yaml", ".xml", ".gradle", ".properties"}
        for file in files:
            if file.suffix.lower() in searchable_extensions or file.name in {"requirements.txt", "Dockerfile"}:
                if token in self._safe_read_text(file).lower():
                    return True
        return False
