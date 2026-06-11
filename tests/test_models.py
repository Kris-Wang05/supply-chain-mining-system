import unittest

from supply_chain_mining.models import Candidate


class CandidateModelTests(unittest.TestCase):
    def test_candidate_requires_mispricing_hypothesis_for_ab_rating(self) -> None:
        payload = {
            "ticker": "TEST",
            "exchange": "NASDAQ",
            "region": "US",
            "node": "critical node",
            "transmission_type": "capacity-gap",
            "order_inevitability": 4,
            "purity_pct": ">30%",
            "coverage_test": {
                "coverage_density": "pass",
                "rerating_check": "pass",
                "keyword_density": "pass",
            },
            "kill_rules_triggered": [],
            "price_history_note": "No independent rerating observed.",
            "rating": "A",
        }

        with self.assertRaisesRegex(ValueError, "mispricing_hypothesis"):
            Candidate.from_dict(payload)

    def test_rejected_candidate_requires_kill_rule(self) -> None:
        payload = {
            "ticker": "TEST",
            "exchange": "NASDAQ",
            "region": "US",
            "node": "critical node",
            "transmission_type": "capacity-gap",
            "order_inevitability": 4,
            "purity_pct": ">30%",
            "coverage_test": {
                "coverage_density": "pass",
                "rerating_check": "unknown",
                "keyword_density": "unknown",
            },
            "kill_rules_triggered": [],
            "price_history_note": "Contract source not verified.",
            "rating": "出局",
        }

        with self.assertRaisesRegex(ValueError, "kill_rules_triggered"):
            Candidate.from_dict(payload)

    def test_valid_c_candidate(self) -> None:
        payload = {
            "ticker": "TEST",
            "exchange": "NYSE",
            "region": "US",
            "node": "critical node",
            "transmission_type": "designed-in",
            "order_inevitability": 5,
            "purity_pct": "10-30%",
            "coverage_test": {
                "coverage_density": "pass",
                "rerating_check": "pass",
                "keyword_density": "pass",
            },
            "kill_rules_triggered": [],
            "price_history_note": "Needs source-backed price history review.",
            "rating": "C",
        }

        candidate = Candidate.from_dict(payload)

        self.assertEqual(candidate.ticker, "TEST")

    def test_pending_marker_requires_pending_rating_for_letters(self) -> None:
        payload = {
            "ticker": "TEST",
            "exchange": "NYSE",
            "region": "US",
            "node": "critical node",
            "transmission_type": "designed-in",
            "order_inevitability": 5,
            "purity_pct": "需验证",
            "coverage_test": {
                "coverage_density": "pass",
                "rerating_check": "pass",
                "keyword_density": "pass",
            },
            "kill_rules_triggered": [],
            "price_history_note": "Needs source-backed price history review.",
            "rating": "C",
        }

        with self.assertRaisesRegex(ValueError, "rating=pending"):
            Candidate.from_dict(payload)

    def test_pending_candidate_can_hold_unverified_fields(self) -> None:
        payload = {
            "ticker": "TEST",
            "exchange": "NYSE",
            "region": "US",
            "node": "critical node",
            "transmission_type": "designed-in",
            "order_inevitability": 5,
            "purity_pct": "需验证",
            "coverage_test": {
                "coverage_density": "unknown",
                "rerating_check": "pass",
                "keyword_density": "pass",
            },
            "kill_rules_triggered": [],
            "price_history_note": "pending source",
            "rating": "pending",
        }

        candidate = Candidate.from_dict(payload)

        self.assertEqual(candidate.rating, "pending")


if __name__ == "__main__":
    unittest.main()
