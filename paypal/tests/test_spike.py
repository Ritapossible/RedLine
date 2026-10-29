import httpx
import pytest

import spike
from fake_sandbox import FakeSandbox
from redline_paypal.paypal_api import RestPayPal


def client(sandbox):
    return RestPayPal("id", "secret", transport=httpx.MockTransport(sandbox), sleep=lambda s: None)


def test_the_spike_proves_hold_partial_capture_and_void(tmp_path, capsys):
    sandbox = FakeSandbox()
    out = tmp_path / "spike.json"
    assert spike.main(["spike.py", str(out)], env={}, paypal=client(sandbox)) == 0
    import json
    record = json.loads(out.read_text())
    step = record["steps"]["partial_capture_then_void"]
    assert step["captured_cents"] == 750 and step["released_cents"] == 1250 and step["adds_up"]
    assert step["status_after_capture"] == "PARTIALLY_CAPTURED" and step["status_after_void"] == "VOIDED"
    assert record["steps"]["reauthorize_inside_honor_period"]["result"] == "refused"
    assert record["steps"]["void_whole_hold"]["status_at_end"] == "VOIDED"
    # No hold is left open by the spike.
    assert all(a["status"] in ("VOIDED", "CAPTURED") for a in sandbox.auths.values())


def test_no_payer_details_leave_the_client():
    import dataclasses
    from redline_paypal.paypal_api import Hold, Op
    assert {f.name for f in dataclasses.fields(Hold)} == {"id", "status", "amount_cents", "currency", "created", "expires"}
    assert {f.name for f in dataclasses.fields(Op)} == {"id", "status", "amount_cents", "currency", "final"}


def test_a_write_is_idempotent_by_request_id():
    sandbox = FakeSandbox()
    pp = client(sandbox)
    order, _ = pp.create_order(amount_cents=2000, currency="USD", request_id="o1", card={"number": "4111"})
    h = pp.authorize_order(order, request_id="a1")
    c1 = pp.capture(h.id, amount_cents=500, currency="USD", final=False, request_id="c1")
    c2 = pp.capture(h.id, amount_cents=500, currency="USD", final=False, request_id="c1")
    assert c1.id == c2.id and sandbox.auths[h.id]["captured"] == 500


def test_live_paypal_is_refused():
    with pytest.raises(ValueError):
        RestPayPal("id", "secret", base_url="https://api-m.paypal.com")
