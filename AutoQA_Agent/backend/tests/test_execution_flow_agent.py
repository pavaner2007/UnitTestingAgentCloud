"""
Tests for ExecutionFlowAgent.

Tests verify:
- Basic single-hop flow construction
- DB call detection
- External HTTP call detection
- Confidence score validity range
- Graceful handling of empty inputs
"""
from __future__ import annotations

import ast
import textwrap
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agents.execution_flow_agent import (
    ExecutionFlowAgent,
    _is_db_call,
    _is_http_call,
    _extract_function_body_calls,
    _find_function_in_tree,
    _get_attribute_chain,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_HANDLER = textwrap.dedent("""\
def login(request):
    user = db.query(User).filter_by(email=request.email).first()
    if not user:
        raise ValueError("User not found")
    token = jwt_service.generate_token(user.id)
    result = requests.get("https://external.api/verify")
    return token
""")

SAMPLE_SERVICE = textwrap.dedent("""\
def generate_token(user_id):
    payload = {"sub": user_id}
    return jwt.encode(payload, SECRET_KEY)
""")


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestAttributeChain:
    def test_simple_attribute(self):
        code = "db.query(User)"
        tree = ast.parse(code, mode="eval")
        call = tree.body
        chain = _get_attribute_chain(call.func)
        assert "db" in chain
        assert "query" in chain

    def test_nested_attribute(self):
        code = "self.db.query(User)"
        tree = ast.parse(code, mode="eval")
        call = tree.body
        chain = _get_attribute_chain(call.func)
        assert len(chain) >= 2


class TestDbCallDetection:
    def test_detects_sqlalchemy_query(self):
        code = "db.query(User)"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_db_call(call_node) is True

    def test_detects_session_execute(self):
        code = "session.execute(stmt)"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_db_call(call_node) is True

    def test_does_not_flag_print(self):
        code = "print('hello')"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_db_call(call_node) is False

    def test_does_not_flag_regular_function(self):
        code = "some_service.process(data)"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_db_call(call_node) is False


class TestHttpCallDetection:
    def test_detects_requests_get(self):
        code = "requests.get('https://example.com')"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_http_call(call_node) is True

    def test_detects_httpx_post(self):
        code = "httpx.post('https://example.com', json=data)"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_http_call(call_node) is True

    def test_does_not_flag_db_call(self):
        code = "db.query(User)"
        tree = ast.parse(code, mode="eval")
        call_node = tree.body
        assert _is_http_call(call_node) is False


class TestExtractFunctionBodyCalls:
    def test_basic_extraction(self):
        code = textwrap.dedent("""\
        def login(request):
            try:
                user = db.query(User).filter_by(email=request.email).first()
                result = requests.get("https://external.api/verify")
            except ValueError as e:
                pass
            return result
        """)
        tree = ast.parse(code)
        calls, db_calls, http_calls, exceptions = _extract_function_body_calls(tree, "login")
        assert len(db_calls) >= 1, "Should detect db.query call"
        assert len(http_calls) >= 1, "Should detect requests.get call"
        assert "ValueError" in exceptions

    def test_returns_empty_for_nonexistent_function(self):
        tree = ast.parse(SAMPLE_HANDLER)
        calls, db_calls, http_calls, exceptions = _extract_function_body_calls(tree, "nonexistent_func")
        assert calls == []
        assert db_calls == []
        assert http_calls == []
        assert exceptions == []

    def test_detects_all_exception_types(self):
        code = textwrap.dedent("""\
        def my_func():
            try:
                pass
            except (ValueError, TypeError) as e:
                pass
            except RuntimeError:
                pass
        """)
        tree = ast.parse(code)
        _, _, _, exceptions = _extract_function_body_calls(tree, "my_func")
        assert "ValueError" in exceptions
        assert "TypeError" in exceptions
        assert "RuntimeError" in exceptions


class TestFindFunctionInTree:
    def test_finds_top_level_function(self):
        tree = ast.parse(SAMPLE_HANDLER)
        line_no, class_name = _find_function_in_tree(tree, "login")
        assert line_no == 1
        assert class_name is None

    def test_returns_none_for_missing_function(self):
        tree = ast.parse(SAMPLE_HANDLER)
        line_no, class_name = _find_function_in_tree(tree, "missing_func")
        assert line_no is None

    def test_finds_class_method(self):
        code = textwrap.dedent("""\
        class AuthService:
            def authenticate(self, email, password):
                pass
        """)
        tree = ast.parse(code)
        line_no, class_name = _find_function_in_tree(tree, "authenticate")
        assert line_no is not None
        assert class_name == "AuthService"


class TestExecutionFlowAgent:
    def test_empty_api_inventory(self):
        agent = ExecutionFlowAgent()
        results = agent.build_all_flows(
            api_inventory=[],
            repo_path=Path("."),
            dep_graph=None,
            code_insights=None,
        )
        assert results == []
        assert isinstance(results, list)

    def test_returns_list_of_execution_flow_results(self, tmp_path):
        # Write a minimal Python handler file
        handler_code = textwrap.dedent("""\
        def get_users():
            users = db.query(User).all()
            return users
        """)
        handler_file = tmp_path / "routes.py"
        handler_file.write_text(handler_code)

        agent = ExecutionFlowAgent()
        api_inventory = [{
            "method": "GET",
            "path": "/users",
            "file": "routes.py",
            "function_name": "get_users",
        }]
        results = agent.build_all_flows(
            api_inventory=api_inventory,
            repo_path=tmp_path,
            dep_graph=None,
            code_insights=None,
        )
        assert len(results) == 1
        flow = results[0]
        assert flow.entry_point == "GET /users"
        assert len(flow.nodes) >= 1

    def test_confidence_score_in_range(self, tmp_path):
        handler_code = textwrap.dedent("""\
        def do_something():
            result = db.execute('SELECT 1')
            return result
        """)
        (tmp_path / "handler.py").write_text(handler_code)

        agent = ExecutionFlowAgent()
        api_inventory = [{
            "method": "POST",
            "path": "/action",
            "file": "handler.py",
            "function_name": "do_something",
        }]
        results = agent.build_all_flows(
            api_inventory=api_inventory,
            repo_path=tmp_path,
            dep_graph=None,
            code_insights=None,
        )
        for flow in results:
            assert 0.0 <= flow.confidence_score <= 1.0, "Confidence must be in [0, 1]"
            for node in flow.nodes:
                assert 0.0 <= node.confidence <= 1.0

    def test_db_operations_counted(self, tmp_path):
        handler_code = textwrap.dedent("""\
        def create_user():
            user = db.query(User).first()
            db.add(user)
            db.commit()
        """)
        (tmp_path / "users.py").write_text(handler_code)

        agent = ExecutionFlowAgent()
        api_inventory = [{
            "method": "POST",
            "path": "/users",
            "file": "users.py",
            "function_name": "create_user",
        }]
        results = agent.build_all_flows(
            api_inventory=api_inventory,
            repo_path=tmp_path,
            dep_graph=None,
            code_insights=None,
        )
        assert len(results) == 1
        assert results[0].db_operations_count >= 1

    def test_http_calls_counted(self, tmp_path):
        handler_code = textwrap.dedent("""\
        def verify_payment():
            resp = requests.post('https://api.stripe.com/v1/charges', data={})
            return resp.json()
        """)
        (tmp_path / "payment.py").write_text(handler_code)

        agent = ExecutionFlowAgent()
        api_inventory = [{
            "method": "POST",
            "path": "/payment/verify",
            "file": "payment.py",
            "function_name": "verify_payment",
        }]
        results = agent.build_all_flows(
            api_inventory=api_inventory,
            repo_path=tmp_path,
            dep_graph=None,
            code_insights=None,
        )
        assert len(results) == 1
        assert results[0].external_http_calls_count >= 1

    def test_max_endpoints_capped_at_20(self, tmp_path):
        """Agent should process at most 20 endpoints to keep analysis bounded."""
        api_inventory = [
            {"method": "GET", "path": f"/resource/{i}", "file": "", "function_name": ""}
            for i in range(30)
        ]
        agent = ExecutionFlowAgent()
        results = agent.build_all_flows(
            api_inventory=api_inventory,
            repo_path=tmp_path,
            dep_graph=None,
            code_insights=None,
        )
        # Only 20 should be processed (no file = no handler = flow with 1 root node each)
        assert len(results) <= 20
