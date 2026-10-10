"""The deployed files: what they are built from, that they fit, and the
structural rules a reviewer would check by reading them."""

import ast
import builtins
import os
import subprocess
import sys

import pytest

from minify_contract import _names_used, minify

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, "contracts", "build")
RUNNER = "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"
CAP = 16_777_216
GENLAYER = {"gl", "Address", "u256", "TreeMap", "DynArray"}


def read(name):
    with open(os.path.join(BUILD, name)) as h:
        return h.read()


@pytest.fixture(scope="module")
def treasury():
    subprocess.run([sys.executable, os.path.join(ROOT, "deploy", "build_contract.py")], check=True, capture_output=True)
    return read("redline.py")


@pytest.fixture(scope="module")
def watcher(treasury):
    return read("redline_watcher.py")


@pytest.fixture(scope="module", params=[("redline", "RedLine"), ("redline_watcher", "RedLineWatcher")])
def pair(request, treasury):
    name, root = request.param
    return read(name + ".py"), read(name + ".min.py"), root


def method(src, name):
    start = src.index("    def %s(" % name)
    rest = src[start + 10 :]
    ends = [i for i in (rest.find("\n    @gl."), rest.find("\n    def ")) if i != -1]
    return src[start : start + 10 + min(ends)] if ends else src[start:]


def closures(src, name):
    body = method(src, name)
    leader = body[body.index("def leader"): body.index("def validator")]
    validator = body[body.index("def validator"): body.index("gl.vm.run_nondet")]
    return body, leader, validator


def test_runner_header_then_code(pair):
    for src in pair[:2]:
        lines = src.splitlines()
        assert lines[0] == '# { "Depends": "%s" }' % RUNNER
        assert lines[1] == "from genlayer import *"


def test_deployed_is_a_fresh_minify_of_the_tested_build(pair):
    readable, deployed, root = pair
    assert minify(readable, root=root)[0] == deployed


def test_every_name_the_deployed_file_uses_is_defined(pair):
    tree = ast.parse(pair[1])
    defined = set(GENLAYER) | set(dir(builtins))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            defined |= {(a.asname or a.name).split(".")[0] for a in node.names if a.name != "*"}
    missing = set()
    for node in tree.body:
        missing |= _names_used(node) - defined
    assert not missing, sorted(missing)


def test_it_fits_bradburys_gas_cap(pair):
    """Measured on Bradbury: a deploy costs about 0.96M gas plus 782 per byte
    of code and arguments, against 2^24."""
    size = len(pair[1].encode("utf-8"))
    assert 960_000 + 782 * (size + 100) < CAP * 0.96, size


def test_the_fetch_is_inline_in_every_closure(watcher):
    for name in ("pin", "observe"):
        _body, leader, validator = closures(watcher, name)
        for closure in (leader, validator):
            assert "gl.nondet.web.get(uri)" in closure
            assert "_status in MISSING_STATUS" in closure and "200 <= _status < 300" in closure
            assert "page_text(_resp.body" in closure


def test_pinning_runs_no_model_and_checking_asks_only_about_missing_passages(watcher):
    _body, leader, validator = closures(watcher, "pin")
    assert "exec_prompt" not in leader and "exec_prompt" not in validator
    _body, leader, validator = closures(watcher, "observe")
    for closure in (leader, validator):
        before_model = closure[: closure.index("exec_prompt")]
        assert "passage_present(_text, _p[1])" in before_model and "continue" in before_model


def test_validators_compare_what_is_on_the_page_exactly_and_the_finding_through_the_rule(watcher):
    _body, _leader, validator = closures(watcher, "pin")
    assert 'str(_theirs.get("page", "")) == _page and list(_theirs.get("found", [])) == _found' in validator
    _body, _leader, validator = closures(watcher, "observe")
    assert 'str(_theirs.get("page", "")) != _page' in validator
    assert "_leader_present != _mine_present" in validator
    assert "jury_agrees(leader_kind=" in validator


def test_the_treasury_never_reads_the_watcher_and_runs_no_model(treasury):
    assert ".view()" not in treasury
    assert "exec_prompt" not in treasury and "run_nondet" not in treasury and "web.get" not in treasury
    # Its one link to the watcher is a message, sent when a cover is funded.
    assert treasury.count("gl.get_contract_at(") == 1
    assert '.emit(on="accepted").pin(' in method(treasury, "open_cover")


def test_only_the_watcher_may_report_and_it_holds_no_gen(treasury, watcher):
    for name in ("note_pin", "note_check"):
        assert "self._from_watcher()" in method(treasury, name)
    assert "payable" not in watcher and "emit_transfer" not in watcher


def test_only_withdraw_moves_value_and_payable_calls_never_revert(treasury):
    assert treasury.count("emit_transfer(") == 1
    assert "emit_transfer(" in method(treasury, "withdraw")
    assert treasury.count("@gl.public.write.payable") == 1
    body = method(treasury, "open_cover")
    before_save = body[: body.index("self._save(cover)")]
    assert "raise" not in before_save  # value has arrived: refuse and credit back, never revert
    assert "self._refuse(" in before_save


def test_settle_and_withdraw_read_no_other_contract(treasury):
    for name in ("settle", "withdraw", "accept", "cancel"):
        assert "get_contract_at" not in method(treasury, name), name
