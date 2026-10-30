"""Billing shape tests: monthly checkout carries the 14-day trial, /pricing says so."""

import http.client
import pathlib
import tempfile
import threading
import unittest
import urllib.request

from agent_visibility import web


class BillingTests(unittest.TestCase):
    def test_monthly_checkout_carries_trial_and_pricing_notes_it(self):
        env = {
            "STRIPE_SECRET_KEY": "sk_test_x",
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "STRIPE_PRICES": "starter=price_123,growth=price_456",
            "PUBLIC_URL": "https://example.test",
        }
        with tempfile.TemporaryDirectory() as t:
            srv = web.make_server("127.0.0.1", 0, pathlib.Path(t), env=env)
            billing = srv.RequestHandlerClass.billing
            sent = {}
            billing._stripe = lambda path, form: sent.update(form) or {"url": "https://checkout.test/s"}
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            try:
                conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=30)
                conn.request("POST", "/billing/checkout", "plan=growth")
                res = conn.getresponse()
                self.assertEqual((res.status, res.getheader("Location")), (303, "https://checkout.test/s"))
                conn.close()
                self.assertEqual(sent["mode"], "subscription")
                self.assertEqual(sent["subscription_data[trial_period_days]"], "14")
                self.assertEqual(sent["line_items[0][price]"], "price_456")
                page = urllib.request.urlopen(base + "/pricing", timeout=30).read().decode()
                self.assertIn("14-day free trial", page)
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
