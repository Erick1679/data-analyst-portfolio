"""Isolated tests for endpoint risk classification."""

from django.test import SimpleTestCase

from .security_endpoint_risk import (
    A_CANDIDATE,
    B,
    D_CANDIDATE,
    E,
    UNCLASSIFIED,
    classify_endpoint_risk,
)


class EndpointRiskClassificationTests(SimpleTestCase):
    """Test endpoint classifications without database access."""

    EXPECTED = (
        ("analytics", "dashboard", "GET", A_CANDIDATE),
        ("analytics", "indicator_api", "GET", A_CANDIDATE),
        ("analytics", "places_api", "GET", A_CANDIDATE),

        ("organizations", "corporate_dashboard", "GET", B),

        ("retail", "product_list", "GET", B),
        ("retail", "branch_list", "GET", B),

        ("datasets", "dataset_list", "GET", B),
        ("datasets", "dataset_list", "POST", D_CANDIDATE),
        ("datasets", "dataset_detail", "GET", B),

        ("datasets", "grant_list", "POST", E),
        ("datasets", "grant_revoke", "POST", E),

        ("organizations", "membership_list", "POST", E),
        ("organizations", "membership_role_change", "POST", E),
        ("organizations", "membership_deactivate", "POST", E),

        ("auditlog", "audit_history", "GET", E),
    )

    def test_all_fifteen_approved_mappings(self):
        self.assertEqual(len(self.EXPECTED), 15)

        for app, handler, method, expected in self.EXPECTED:
            with self.subTest(
                app=app,
                handler=handler,
                method=method,
            ):
                self.assertEqual(
                    classify_endpoint_risk(app, handler, method),
                    expected,
                )

    def test_unknown_application_is_unclassified(self):
        self.assertEqual(
            classify_endpoint_risk("unknown", "dashboard", "GET"),
            UNCLASSIFIED,
        )

    def test_unknown_handler_is_unclassified(self):
        self.assertEqual(
            classify_endpoint_risk("datasets", "unknown", "GET"),
            UNCLASSIFIED,
        )

    def test_unsupported_method_is_unclassified(self):
        self.assertEqual(
            classify_endpoint_risk("datasets", "dataset_detail", "POST"),
            UNCLASSIFIED,
        )

    def test_method_case_is_normalized(self):
        self.assertEqual(
            classify_endpoint_risk("retail", "product_list", "get"),
            B,
        )

    def test_method_whitespace_is_normalized(self):
        self.assertEqual(
            classify_endpoint_risk("retail", "branch_list", " GET "),
            B,
        )

    def test_empty_method_is_unclassified(self):
        self.assertEqual(
            classify_endpoint_risk("retail", "branch_list", ""),
            UNCLASSIFIED,
        )

    def test_non_string_input_is_unclassified(self):
        inputs = (
            (None, "dashboard", "GET"),
            ("analytics", None, "GET"),
            ("analytics", "dashboard", None),
            (123, "dashboard", "GET"),
            ("analytics", "dashboard", 123),
        )

        for app, handler, method in inputs:
            with self.subTest(
                app=app,
                handler=handler,
                method=method,
            ):
                self.assertEqual(
                    classify_endpoint_risk(app, handler, method),
                    UNCLASSIFIED,
                )

    def test_dataset_get_and_post_are_distinct(self):
        self.assertEqual(
            classify_endpoint_risk(
                "datasets", "dataset_list", "GET"
            ),
            B,
        )
        self.assertEqual(
            classify_endpoint_risk(
                "datasets", "dataset_list", "POST"
            ),
            D_CANDIDATE,
        )

    def test_privileged_operations_are_category_e(self):
        operations = (
            ("datasets", "grant_list"),
            ("datasets", "grant_revoke"),
            ("organizations", "membership_list"),
            ("organizations", "membership_role_change"),
            ("organizations", "membership_deactivate"),
        )

        for app, handler in operations:
            with self.subTest(app=app, handler=handler):
                self.assertEqual(
                    classify_endpoint_risk(app, handler, "POST"),
                    E,
                )

    def test_privileged_operations_do_not_downgrade_on_get(self):
        operations = (
            ("datasets", "grant_list"),
            ("datasets", "grant_revoke"),
            ("organizations", "membership_list"),
            ("organizations", "membership_role_change"),
            ("organizations", "membership_deactivate"),
        )

        for app, handler in operations:
            with self.subTest(app=app, handler=handler):
                self.assertEqual(
                    classify_endpoint_risk(app, handler, "GET"),
                    UNCLASSIFIED,
                )

    def test_admin_endpoint_remains_unclassified(self):
        self.assertEqual(
            classify_endpoint_risk("admin", "index", "GET"),
            UNCLASSIFIED,
        )

    def test_identifier_matching_is_exact(self):
        self.assertEqual(
            classify_endpoint_risk(
                "retail", "product_list_extra", "GET"
            ),
            UNCLASSIFIED,
        )

    def test_application_names_are_not_guessed(self):
        self.assertEqual(
            classify_endpoint_risk(
                "Retail", "product_list", "GET"
            ),
            UNCLASSIFIED,
        )

    def test_head_does_not_inherit_get_category(self):
        self.assertEqual(
            classify_endpoint_risk(
                "analytics", "dashboard", "HEAD"
            ),
            UNCLASSIFIED,
        )

    def test_options_does_not_inherit_get_category(self):
        self.assertEqual(
            classify_endpoint_risk(
                "analytics", "dashboard", "OPTIONS"
            ),
            UNCLASSIFIED,
        )
