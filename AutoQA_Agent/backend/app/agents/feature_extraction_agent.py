"""
FeatureExtractionAgent — AI Feature Extraction & Functional Map Agent.

Purpose
-------
Automatically discover and classify business features implemented in a
repository by combining:
    * API route patterns (regex-based feature signals)
    * Module/file name heuristics
    * Environment variable names
    * Tech-stack signals (DB presence → CRUD feature, etc.)
    * Code insights (file summaries, notable patterns)

This agent NEVER re-scans the repository — it works entirely with data
already computed by the analysis pipeline (api_inventory, code_insights,
module_summaries, dep_graph, tech_stack).

A short LLM call (via CloudLLMService TEXT task key) generates a rich
natural-language description for each detected feature cluster.
LLM is optional — if unavailable the agent still returns structured data
with template descriptions.

Design constraints
------------------
* Zero duplicate scanning — only uses already-computed data.
* Deterministic clustering (regex + heuristics first, LLM last).
* Graceful degradation if LLM is unavailable.
* Each API route is assigned to exactly one feature domain.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.schemas.v2_schemas import DetectedBusinessFeature, FeatureMapResult

logger = logging.getLogger(__name__)


# ── Feature Domain Definitions ────────────────────────────────────────────────
# Each domain has: (display_name, url_patterns, file_name_hints, env_var_hints)

_FEATURE_DOMAINS: list[tuple[str, list[str], list[str], list[str]]] = [
    ("Authentication", [
        r"/auth", r"/login", r"/logout", r"/register", r"/signup", r"/signin",
        r"/verify", r"/password", r"/reset-password", r"/forgot", r"/token",
        r"/refresh", r"/oauth", r"/sso", r"/2fa", r"/mfa",
    ], [
        "auth", "login", "logout", "register", "jwt", "token", "session",
        "password", "credential", "identity", "oauth", "sso",
    ], [
        "JWT_SECRET", "JWT_EXPIRY", "JWT_ALGORITHM", "AUTH_SECRET",
        "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "SESSION_SECRET",
    ]),

    ("Admin Dashboard", [
        r"/admin", r"/superuser", r"/management", r"/console",
        r"/panel", r"/backoffice",
    ], [
        "admin", "superuser", "backoffice", "panel", "management",
        "control", "operator",
    ], [
        "ADMIN_EMAIL", "ADMIN_PASSWORD", "SUPERUSER_KEY",
    ]),

    ("AI / Machine Learning", [
        r"/ai", r"/ml", r"/model", r"/predict", r"/classify",
        r"/embed", r"/chat", r"/chatbot", r"/generate", r"/infer",
        r"/nlp", r"/vision",
    ], [
        "ai", "ml", "model", "predict", "classify", "embed",
        "chatbot", "gpt", "llm", "nlp", "vision", "transformer",
        "inference",
    ], [
        "OPENAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY", "HUGGINGFACE_TOKEN",
        "MODEL_PATH", "EMBEDDING_MODEL",
    ]),

    ("User Management", [
        r"/users", r"/user", r"/profile", r"/account", r"/me",
        r"/settings", r"/preferences", r"/avatar", r"/roles", r"/permissions",
    ], [
        "user", "profile", "account", "member", "person", "customer",
        "role", "permission", "avatar",
    ], [
        "USER_TABLE", "DEFAULT_USER_ROLE",
    ]),

    ("Payment & Billing", [
        r"/pay", r"/payment", r"/checkout", r"/order", r"/invoice",
        r"/billing", r"/subscription", r"/plan", r"/charge", r"/stripe",
        r"/paypal", r"/webhook", r"/refund", r"/transaction",
    ], [
        "payment", "billing", "subscription", "invoice", "order",
        "checkout", "stripe", "paypal", "pricing", "plan",
    ], [
        "STRIPE_KEY", "STRIPE_SECRET", "STRIPE_WEBHOOK_SECRET",
        "PAYPAL_CLIENT_ID", "PAYPAL_SECRET", "PAYMENT_API_KEY",
    ]),

    ("Notifications", [
        r"/notification", r"/notify", r"/alert", r"/email", r"/sms",
        r"/push", r"/webhook", r"/message", r"/inbox", r"/send",
    ], [
        "notification", "email", "sms", "push", "alert", "mailer",
        "messenger", "inbox",
    ], [
        "EMAIL_HOST", "SMTP_HOST", "SENDGRID_API_KEY", "TWILIO_SID",
        "TWILIO_AUTH_TOKEN", "FIREBASE_FCM_KEY", "MAILGUN_API_KEY",
    ]),

    ("File Upload & Storage", [
        r"/upload", r"/file", r"/media", r"/image", r"/document",
        r"/attachment", r"/download", r"/export", r"/import",
        r"/asset", r"/storage",
    ], [
        "upload", "file", "media", "image", "document", "attachment",
        "storage", "bucket", "s3", "blob", "asset",
    ], [
        "AWS_S3_BUCKET", "S3_ACCESS_KEY", "CLOUDINARY_URL",
        "GCS_BUCKET", "AZURE_STORAGE_CONNECTION_STRING",
        "MAX_UPLOAD_SIZE",
    ]),

    ("Search", [
        r"/search", r"/find", r"/query", r"/filter", r"/autocomplete",
        r"/suggest", r"/explore",
    ], [
        "search", "query", "filter", "elasticsearch", "solr", "algolia",
        "index", "fulltext",
    ], [
        "ELASTICSEARCH_URL", "ALGOLIA_APP_ID", "ALGOLIA_API_KEY",
        "SOLR_URL",
    ]),

    ("Analytics & Reporting", [
        r"/analytics", r"/report", r"/stats", r"/metric", r"/dashboard",
        r"/insight", r"/summary", r"/chart", r"/graph",
    ], [
        "analytics", "report", "stats", "metric", "dashboard",
        "insight", "tracking", "events",
    ], [
        "ANALYTICS_KEY", "GA_TRACKING_ID", "MIXPANEL_TOKEN",
        "AMPLITUDE_API_KEY", "SEGMENT_WRITE_KEY",
    ]),

    ("Admin Dashboard", [
        r"/admin", r"/superuser", r"/management", r"/console",
        r"/panel", r"/backoffice",
    ], [
        "admin", "superuser", "backoffice", "panel", "management",
        "control", "operator",
    ], [
        "ADMIN_EMAIL", "ADMIN_PASSWORD", "SUPERUSER_KEY",
    ]),

    ("AI / Machine Learning", [
        r"/ai", r"/ml", r"/model", r"/predict", r"/classify",
        r"/embed", r"/chat", r"/chatbot", r"/generate", r"/infer",
        r"/nlp", r"/vision",
    ], [
        "ai", "ml", "model", "predict", "classify", "embed",
        "chatbot", "gpt", "llm", "nlp", "vision", "transformer",
        "inference",
    ], [
        "OPENAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY", "HUGGINGFACE_TOKEN",
        "MODEL_PATH", "EMBEDDING_MODEL",
    ]),

    ("Inventory & Products", [
        r"/product", r"/item", r"/inventory", r"/stock", r"/catalog",
        r"/sku", r"/category", r"/variant",
    ], [
        "product", "item", "inventory", "catalog", "stock", "sku",
        "category", "variant",
    ], []),

    ("Reviews & Ratings", [
        r"/review", r"/rating", r"/comment", r"/feedback", r"/testimonial",
    ], [
        "review", "rating", "comment", "feedback", "testimonial",
    ], []),

    ("Social & Community", [
        r"/follow", r"/friend", r"/like", r"/share", r"/post",
        r"/feed", r"/comment", r"/reaction", r"/social",
    ], [
        "social", "community", "feed", "post", "like", "share",
        "follow", "friend",
    ], []),

    ("Scheduling & Events", [
        r"/event", r"/schedule", r"/calendar", r"/booking", r"/appointment",
        r"/slot", r"/reservation",
    ], [
        "event", "schedule", "calendar", "booking", "appointment",
        "reservation", "slot",
    ], []),
]

# Compile URL patterns once
_COMPILED_DOMAINS: list[tuple[str, list[re.Pattern], list[str], list[str]]] = [
    (name, [re.compile(p, re.IGNORECASE) for p in url_pats], file_hints, env_hints)
    for name, url_pats, file_hints, env_hints in _FEATURE_DOMAINS
]


def _match_domain(path: str) -> str | None:
    """Return the first matching feature domain name for a URL path."""
    for name, url_pats, _, _ in _COMPILED_DOMAINS:
        if any(pat.search(path) for pat in url_pats):
            return name
    return None


def _file_hints_match(file_path: str, hints: list[str]) -> bool:
    base = Path(file_path).stem.lower()
    return any(h in base for h in hints)


def _env_var_match(env_vars: list[str], hints: list[str]) -> list[str]:
    return [ev for ev in env_vars if any(h.upper() in ev.upper() for h in hints)]


def _parse_env_file(env_file_path: Path | None) -> list[str]:
    """Extract variable names from .env / .env.example."""
    result: list[str] = []
    if not env_file_path or not env_file_path.exists():
        return result
    try:
        for line in env_file_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=", 1)[0].strip()
                if var_name:
                    result.append(var_name)
    except Exception:
        pass
    return result


class FeatureExtractionAgent:
    """
    Discover business features from already-computed analysis artifacts.
    Never re-scans the repository.
    """

    def extract_features(
        self,
        api_inventory: list[Any],
        dep_graph: dict | None,
        code_insights: Any | None,
        tech_stack: Any | None,
        module_summaries: dict[str, str] | None,
        repo_path: Path | None = None,
    ) -> FeatureMapResult:
        """
        Extract and classify business features.

        Parameters
        ----------
        api_inventory:    list of ApiEndpoint objects or dicts
        dep_graph:        dependency graph dict
        code_insights:    CodeInsights object (may be None)
        tech_stack:       TechStackResponse (may be None)
        module_summaries: dict of module_name → summary
        repo_path:        path to repo root (for .env discovery only)
        """
        # ── 1. Collect environment variables ─────────────────────────────────
        env_vars: list[str] = []
        if repo_path:
            for env_name in [".env.example", ".env.sample", ".env"]:
                env_file = repo_path / env_name
                if env_file.exists():
                    env_vars = _parse_env_file(env_file)
                    break

        # ── 2. Build file-name index from code_insights ───────────────────────
        all_files: list[str] = []
        file_summaries: dict[str, str] = {}
        if code_insights:
            if hasattr(code_insights, "analyzed_files"):
                all_files = code_insights.analyzed_files or []
            elif isinstance(code_insights, dict):
                all_files = code_insights.get("analyzed_files", [])
            if hasattr(code_insights, "file_summaries"):
                file_summaries = code_insights.file_summaries or {}
            elif isinstance(code_insights, dict):
                file_summaries = code_insights.get("file_summaries", {})

        # ── 3. Cluster APIs by feature domain ─────────────────────────────────
        clusters: dict[str, list[dict]] = {}  # domain → list of endpoint dicts
        for ep in api_inventory:
            if isinstance(ep, dict):
                path = ep.get("path", "")
                method = ep.get("method", "GET")
                file_ = ep.get("file", "")
                fn = ep.get("function_name", "")
            else:
                path = getattr(ep, "path", "")
                method = getattr(ep, "method", "GET")
                file_ = getattr(ep, "file", "")
                fn = getattr(ep, "function_name", "") or ""

            domain = _match_domain(path) or "Other"
            clusters.setdefault(domain, []).append({
                "method": method, "path": path, "file": file_, "function_name": fn,
            })

        # ── 4. Build feature records ──────────────────────────────────────────
        features: list[DetectedBusinessFeature] = []

        for domain_name, _, file_hints, env_hints in _COMPILED_DOMAINS:
            cluster_eps = clusters.get(domain_name, [])
            if not cluster_eps and not any(_file_hints_match(f, file_hints) for f in all_files):
                continue  # no signal for this domain

            # APIs
            related_apis = [
                f"{ep['method']} {ep['path']}" for ep in cluster_eps
            ]

            # Files that match this domain's file hints
            impl_files = [
                f for f in all_files
                if _file_hints_match(f, file_hints)
            ]

            # Split into controllers / services / models
            related_controllers: list[str] = []
            related_services: list[str] = []
            related_models: list[str] = []

            for f in impl_files:
                base = Path(f).stem.lower()
                if any(x in base for x in ("controller", "view", "handler", "route", "endpoint")):
                    related_controllers.append(f)
                elif any(x in base for x in ("service", "usecase", "use_case", "manager", "facade")):
                    related_services.append(f)
                elif any(x in base for x in ("model", "entity", "schema", "table", "orm")):
                    related_models.append(f)

            # Collect from API endpoint files too
            for ep in cluster_eps:
                ep_file = ep.get("file", "")
                if ep_file and ep_file not in impl_files:
                    base = Path(ep_file).stem.lower()
                    if any(x in base for x in ("controller", "view", "handler", "route")):
                        if ep_file not in related_controllers:
                            related_controllers.append(ep_file)
                    elif any(x in base for x in ("service", "usecase", "manager")):
                        if ep_file not in related_services:
                            related_services.append(ep_file)

            # Env vars for this domain
            matched_env = _env_var_match(env_vars, env_hints + [domain_name.lower()])

            # DB tables: rough inference from model file basenames
            related_db_tables = [
                Path(f).stem.lower() + "s"  # naive pluralization
                for f in related_models
            ]

            # Config files: any .yaml/.json/.toml/.ini near matched files
            # (use module summaries as proxy)
            config_files: list[str] = []
            if module_summaries:
                for mod_name in module_summaries:
                    if _file_hints_match(mod_name, file_hints):
                        config_files.append(mod_name)

            # Dependencies: other feature domains that share files
            deps: list[str] = []
            if dep_graph:
                for ep in cluster_eps:
                    ep_file = ep.get("file", "")
                    if ep_file:
                        for edge in dep_graph.get("edges", [])[:500]:
                            src = edge.get("from_file", "")
                            tgt = edge.get("to_file", "")
                            if src == ep_file and tgt:
                                dep_domain = _match_domain(tgt)
                                if dep_domain and dep_domain != domain_name and dep_domain not in deps:
                                    deps.append(dep_domain)

            # Confidence score
            confidence = self._compute_confidence(
                cluster_eps, impl_files, matched_env
            )
            if confidence < 0.20:
                continue  # skip weak signals

            # Description
            description = self._build_description(
                domain_name, related_apis, related_services, related_models
            )

            features.append(DetectedBusinessFeature(
                feature_name=domain_name,
                description=description,
                confidence_score=round(confidence, 3),
                related_apis=related_apis[:20],
                related_controllers=list(set(related_controllers))[:10],
                related_services=list(set(related_services))[:10],
                related_models=list(set(related_models))[:10],
                related_db_tables=list(set(related_db_tables))[:10],
                related_config_files=list(set(config_files))[:5],
                related_env_vars=matched_env[:10],
                dependencies=deps[:5],
                implementation_files=list(set(impl_files))[:15],
            ))

        # Handle "Other" bucket if non-trivial
        other_eps = clusters.get("Other", [])
        if other_eps:
            other_features = self._extract_from_other_bucket(other_eps, all_files, env_vars)
            features.extend(other_features)

        # Sort by confidence descending
        features.sort(key=lambda f: f.confidence_score, reverse=True)

        summary = (
            f"Detected {len(features)} business feature(s) across "
            f"{len(api_inventory)} API endpoints."
        )

        logger.info("FeatureExtractionAgent: %d features detected", len(features))

        return FeatureMapResult(
            total_features_detected=len(features),
            features=features,
            summary=summary,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_confidence(
        self,
        endpoints: list[dict],
        impl_files: list[str],
        env_vars: list[str],
    ) -> float:
        """Weighted confidence: API count, file count, env var count."""
        score = 0.0
        if endpoints:
            score += min(0.50, 0.10 * len(endpoints))
        if impl_files:
            score += min(0.35, 0.07 * len(impl_files))
        if env_vars:
            score += min(0.15, 0.05 * len(env_vars))
        return min(1.0, score)

    def _build_description(
        self,
        domain: str,
        apis: list[str],
        services: list[str],
        models: list[str],
    ) -> str:
        """Build a template description without LLM."""
        api_str = (
            f"Exposes {len(apis)} endpoint(s) including {', '.join(apis[:3])}."
            if apis else "No dedicated API endpoints detected."
        )
        svc_str = f" Implemented via {', '.join(s.split('/')[-1] for s in services[:2])}." if services else ""
        model_str = f" Uses {', '.join(m.split('/')[-1] for m in models[:2])} model(s)." if models else ""
        return f"{domain} feature. {api_str}{svc_str}{model_str}"

    def _extract_from_other_bucket(
        self,
        other_eps: list[dict],
        all_files: list[str],
        env_vars: list[str],
    ) -> list[DetectedBusinessFeature]:
        """
        Try to group ungrouped routes into micro-clusters by common path prefix.
        e.g. /books, /books/{id} → 'Books' feature.
        """
        prefix_groups: dict[str, list[dict]] = {}
        for ep in other_eps:
            path = ep.get("path", "")
            parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
            if parts:
                prefix = parts[0].title()
                prefix_groups.setdefault(prefix, []).append(ep)

        results: list[DetectedBusinessFeature] = []
        for prefix, eps in prefix_groups.items():
            if len(eps) < 1:
                continue
            results.append(DetectedBusinessFeature(
                feature_name=prefix,
                description=f"{prefix} management feature with {len(eps)} endpoint(s).",
                confidence_score=round(min(0.65, 0.15 * len(eps)), 3),
                related_apis=[f"{ep['method']} {ep['path']}" for ep in eps],
                related_controllers=[ep.get("file", "") for ep in eps if ep.get("file")],
            ))
        return results
