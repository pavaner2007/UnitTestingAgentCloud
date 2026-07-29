import ast
import logging
import re
from pathlib import Path

from app.schemas.analysis import ApiEndpoint

logger = logging.getLogger(__name__)


class ApiDiscoveryAgent:
    IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "target", "__pycache__"}
    HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

    def discover(self, repo_path: Path) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        endpoints.extend(self._discover_fastapi_and_flask(repo_path))
        endpoints.extend(self._discover_express(repo_path))
        return self._deduplicate(endpoints)

    def _discover_fastapi_and_flask(self, repo_path: Path) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        for file in self._iter_files(repo_path, {".py"}):
            try:
                tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            except Exception:
                logger.warning("Unable to parse Python file: %s", file)
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        res = self._parse_python_decorator(decorator, file, repo_path, node)
                        if res:
                            if isinstance(res, list):
                                endpoints.extend(res)
                            else:
                                endpoints.append(res)
        return endpoints

    def _parse_python_decorator(self, decorator, file: Path, repo_path: Path, node) -> ApiEndpoint | list[ApiEndpoint] | None:
        if not isinstance(decorator, ast.Call):
            return None
        func = decorator.func
        if not isinstance(func, ast.Attribute):
            return None
        method = func.attr.lower()

        # Support Flask @app.route(..., methods=["GET", "POST"]) syntax
        if method == "route":
            path = self._extract_first_string_arg(decorator)
            if not path:
                return None
            methods = ["GET"]  # Flask route defaults to GET
            for kw in decorator.keywords:
                if kw.arg == "methods":
                    if isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                        methods = []
                        for el in kw.value.elts:
                            if isinstance(el, ast.Constant) and isinstance(el.value, str):
                                methods.append(el.value.upper())
            return [
                ApiEndpoint(
                    method=m,
                    path=path,
                    framework="Flask",
                    file=str(file.relative_to(repo_path)),
                    line_number=getattr(node, "lineno", None),
                    function_name=node.name,
                )
                for m in methods
            ]

        if method not in self.HTTP_METHODS:
            return None
        path = self._extract_first_string_arg(decorator)
        if not path:
            return None
        framework = "FastAPI/Flask"
        return ApiEndpoint(
            method=method.upper(),
            path=path,
            framework=framework,
            file=str(file.relative_to(repo_path)),
            line_number=getattr(node, "lineno", None),
            function_name=node.name,
        )

    def _extract_first_string_arg(self, call_node: ast.Call) -> str | None:
        if call_node.args and isinstance(call_node.args[0], ast.Constant) and isinstance(call_node.args[0].value, str):
            return call_node.args[0].value
        return None

    def _discover_express(self, repo_path: Path) -> list[ApiEndpoint]:
        endpoints: list[ApiEndpoint] = []
        pattern = re.compile(
            r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        )
        for file in self._iter_files(repo_path, {".js", ".ts"}):
            content = file.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(content):
                line_number = content[: match.start()].count("\n") + 1
                endpoints.append(
                    ApiEndpoint(
                        method=match.group(1).upper(),
                        path=match.group(2),
                        framework="Express.js",
                        file=str(file.relative_to(repo_path)),
                        line_number=line_number,
                        function_name=None,
                    )
                )
        return endpoints

    def _iter_files(self, repo_path: Path, extensions: set[str]) -> list[Path]:
        return [
            p for p in repo_path.rglob("*")
            if p.is_file()
            and p.suffix.lower() in extensions
            and not any(part in self.IGNORED_DIRS for part in p.parts)
        ]

    def _deduplicate(self, endpoints: list[ApiEndpoint]) -> list[ApiEndpoint]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[ApiEndpoint] = []
        for endpoint in endpoints:
            key = (endpoint.method, endpoint.path, endpoint.file)
            if key not in seen:
                seen.add(key)
                unique.append(endpoint)
        return unique
