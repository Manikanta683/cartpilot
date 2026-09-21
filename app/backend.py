"""Payment backends.

Two implementations behind one interface:

  MockBackend     — in-memory, returns Razorpay-shaped responses. Zero setup;
                    the whole demo (sell -> gate -> recover) runs with no keys.
                    Mock URLs are clearly fake (rzp.io/mock/...) — no one can
                    mistake them for real charges.
  RazorpayBackend — real Razorpay test-mode REST calls. Needs rzp_test_ keys.

Selected by CARTPILOT_BACKEND env ("mock" default, "razorpay" for real).
"""
import os


class MockBackend:
    """In-memory stand-in with Razorpay-shaped responses."""

    def __init__(self):
        self._orders = {}
        self._links = {}
        self._seq = 0

    def _next(self, prefix):
        self._seq += 1
        return f"{prefix}_mock_{self._seq:04d}"

    def create_order(self, amount_paise, currency="INR", receipt=""):
        oid = self._next("order")
        order = {
            "id": oid,
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt or oid,
            "status": "created",
        }
        self._orders[oid] = order
        return order

    def create_payment_link(self, amount_paise, description,
                            customer_name="", customer_email=""):
        order = self.create_order(amount_paise)
        lid = self._next("plink")
        link = {
            "id": lid,
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "short_url": f"https://rzp.io/mock/{lid}",
            "status": "created",
        }
        self._links[lid] = link
        return link

    def fetch_link(self, link_id):
        return self._links.get(link_id, {"error": "link not found"})

    def simulate_payment(self, link_id, status="paid"):
        """Demo helper: flip a mock link to paid/failed."""
        link = self._links[link_id]
        link["status"] = status
        self._orders[link["order_id"]]["status"] = status
        return link


class RazorpayBackend:
    """Real Razorpay test-mode backend over plain REST."""

    API = "https://api.razorpay.com/v1"

    def __init__(self, key_id, key_secret):
        self.auth = (key_id, key_secret)

    def _post(self, path, payload):
        import httpx
        r = httpx.post(f"{self.API}{path}", auth=self.auth,
                       json=payload, timeout=20)
        r.raise_for_status()
        return r.json()

    def create_order(self, amount_paise, currency="INR", receipt=""):
        return self._post("/orders", {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt or "cartpilot",
        })

    def create_payment_link(self, amount_paise, description,
                            customer_name="", customer_email=""):
        data = self._post("/payment_links", {
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "customer": {
                "name": customer_name or "DemoKart Customer",
                "email": customer_email or "test@example.com",
            },
            "notify": {"sms": False, "email": False},
        })
        return {
            "id": data["id"],
            "order_id": data.get("order_id") or "",
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "short_url": data["short_url"],
            "status": data["status"],
        }

    def fetch_link(self, link_id):
        import httpx
        r = httpx.get(f"{self.API}/payment_links/{link_id}",
                      auth=self.auth, timeout=20)
        r.raise_for_status()
        return r.json()

    def simulate_payment(self, link_id, status="paid"):
        raise NotImplementedError(
            "Real backend: use Razorpay test-mode cards/webhooks to simulate."
        )


_backend = None


def get_backend():
    """Shared backend instance, chosen by CARTPILOT_BACKEND."""
    global _backend
    if _backend is not None:
        return _backend
    which = os.getenv("CARTPILOT_BACKEND", "mock").lower()
    if which == "razorpay":
        from .mcp_client import check_env  # validates rzp_test_ keys
        key_id, key_secret = check_env()
        _backend = RazorpayBackend(key_id, key_secret)
    else:
        _backend = MockBackend()
    return _backend


def reset_backend():
    """For tests — drop the cached instance."""
    global _backend
    _backend = None
