import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend import MockBackend, RazorpayBackend, get_backend, reset_backend


def test_mock_order_and_link():
    b = MockBackend()
    order = b.create_order(99900, receipt="t1")
    assert order["id"].startswith("order_mock_")
    assert order["status"] == "created"
    link = b.create_payment_link(99900, "Test", customer_name="A")
    assert link["short_url"].startswith("https://rzp.io/mock/")
    assert link["order_id"].startswith("order_mock_")


def test_mock_simulate_payment():
    b = MockBackend()
    link = b.create_payment_link(50000, "Test")
    b.simulate_payment(link["id"], status="failed")
    assert b.fetch_link(link["id"])["status"] == "failed"


def test_get_backend_defaults_to_mock():
    reset_backend()
    os.environ.pop("CARTPILOT_BACKEND", None)
    b = get_backend()
    assert isinstance(b, MockBackend)
    reset_backend()


def test_razorpay_backend_holds_auth():
    b = RazorpayBackend("rzp_test_x", "secret")
    assert b.auth == ("rzp_test_x", "secret")
