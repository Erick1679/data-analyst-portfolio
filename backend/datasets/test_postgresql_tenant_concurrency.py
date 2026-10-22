"""PostgreSQL concurrent tenant-integrity regression tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant


class PostgreSQLTenantConcurrencyTests(TransactionTestCase):
    """Verify cross-tenant consistency across committed transactions."""

    databases = {"default"}

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="pg_tenant_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="pg_tenant_recipient",
            password="local-test-password",
        )

        self.org_a = Organization.objects.create(
            name="PostgreSQL Tenant A",
            slug="postgresql-tenant-a",
        )
        self.org_b = Organization.objects.create(
            name="PostgreSQL Tenant B",
            slug="postgresql-tenant-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.org_a,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.org_a,
            created_by=self.owner,
            name="Concurrent Tenant Dataset",
            classification="restricted",
        )

    def test_uncommitted_grant_blocks_membership_reassignment(self):
        import time
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        grant_inserted = Event()
        reassignment_ready = Event()
        release_grant = Event()
        backend_ids = {}

        def issue_grant():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '8s'")
                        cursor.execute("SET LOCAL statement_timeout = '12s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        backend_ids["grant"] = cursor.fetchone()[0]

                    DatasetAccessGrant.objects.create(
                        dataset_id=self.dataset.pk,
                        membership_id=self.membership.pk,
                        granted_by_id=self.owner.pk,
                    )

                    grant_inserted.set()

                    if not release_grant.wait(timeout=10):
                        raise RuntimeError("Grant release timed out.")

                return "grant_committed"
            finally:
                close_old_connections()

        def reassign_membership():
            close_old_connections()
            try:
                if not grant_inserted.wait(timeout=10):
                    raise RuntimeError("Grant insertion did not complete.")

                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '8s'")
                            cursor.execute("SET LOCAL statement_timeout = '12s'")
                            cursor.execute("SELECT pg_backend_pid()")
                            backend_ids["reassignment"] = cursor.fetchone()[0]

                        reassignment_ready.set()

                        OrganizationMembership.objects.filter(
                            pk=self.membership.pk
                        ).update(organization=self.org_b)

                    return "reassignment_committed"
                except IntegrityError:
                    return "reassignment_integrity_rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            grant_future = executor.submit(issue_grant)
            reassignment_future = executor.submit(reassign_membership)
            observed_block = False

            try:
                if not reassignment_ready.wait(timeout=6):
                    if grant_future.done():
                        grant_future.result()
                    if reassignment_future.done():
                        reassignment_future.result()
                    raise RuntimeError("Membership worker was not ready.")

                deadline = time.monotonic() + 5

                with connection.cursor() as cursor:
                    while time.monotonic() < deadline:
                        cursor.execute(
                            "SELECT pg_blocking_pids(%s)",
                            [backend_ids["reassignment"]],
                        )
                        blockers = cursor.fetchone()[0]

                        if backend_ids["grant"] in blockers:
                            observed_block = True
                            break

                        if reassignment_future.done():
                            break

                        time.sleep(0.05)
            finally:
                release_grant.set()

            grant_result = grant_future.result(timeout=15)
            reassignment_result = reassignment_future.result(timeout=15)

        self.membership.refresh_from_db()
        self.dataset.refresh_from_db()

        inconsistent = DatasetAccessGrant.objects.filter(
            membership=self.membership
        ).exclude(
            dataset__organization=self.membership.organization
        )

        self.assertFalse(
            inconsistent.exists(),
            "Concurrent membership change created a cross-tenant grant.",
        )
        self.assertTrue(
            observed_block,
            "PostgreSQL did not confirm membership locking.",
        )
        self.assertEqual(grant_result, "grant_committed")
        self.assertEqual(
            reassignment_result,
            "reassignment_integrity_rejected",
        )

        print(
            "PostgreSQL membership locking regression:",
            grant_result,
            reassignment_result,
            "blocking_confirmed",
        )

    def test_uncommitted_grant_blocks_dataset_reassignment(self):
        import time
        from concurrent.futures import TimeoutError as FutureTimeout
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        grant_inserted = Event()
        reassignment_ready = Event()
        release_grant = Event()
        backend_ids = {}

        def issue_grant():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '8s'")
                        cursor.execute("SET LOCAL statement_timeout = '12s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        backend_ids["grant"] = cursor.fetchone()[0]

                    DatasetAccessGrant.objects.create(
                        dataset_id=self.dataset.pk,
                        membership_id=self.membership.pk,
                        granted_by_id=self.owner.pk,
                    )

                    grant_inserted.set()

                    if not release_grant.wait(timeout=10):
                        raise RuntimeError("Grant release timed out.")

                return "grant_committed"
            finally:
                close_old_connections()

        def reassign_dataset():
            close_old_connections()
            try:
                if not grant_inserted.wait(timeout=10):
                    raise RuntimeError("Grant insertion did not complete.")

                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '8s'")
                        cursor.execute("SET LOCAL statement_timeout = '12s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        backend_ids["reassignment"] = cursor.fetchone()[0]

                    reassignment_ready.set()

                    try:
                        CorporateDataset.objects.filter(
                            pk=self.dataset.pk
                        ).update(organization=self.org_b)
                    except IntegrityError:
                        return "reassignment_integrity_rejected"

                return "reassignment_committed"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            grant_future = executor.submit(issue_grant)
            reassignment_future = executor.submit(reassign_dataset)

            observed_block = False

            try:
                if not reassignment_ready.wait(timeout=6):
                    if grant_future.done():
                        grant_future.result()
                    if reassignment_future.done():
                        reassignment_future.result()
                    raise RuntimeError("Reassignment worker was not ready.")

                deadline = time.monotonic() + 5

                with connection.cursor() as cursor:
                    while time.monotonic() < deadline:
                        cursor.execute(
                            "SELECT pg_blocking_pids(%s)",
                            [backend_ids["reassignment"]],
                        )
                        blockers = cursor.fetchone()[0]

                        if backend_ids["grant"] in blockers:
                            observed_block = True
                            break

                        if reassignment_future.done():
                            break

                        time.sleep(0.05)
            finally:
                release_grant.set()

            grant_result = grant_future.result(timeout=15)
            reassignment_result = reassignment_future.result(timeout=15)

        self.dataset.refresh_from_db()

        inconsistent = DatasetAccessGrant.objects.filter(
            dataset=self.dataset
        ).exclude(
            membership__organization=self.dataset.organization
        )

        self.assertFalse(
            inconsistent.exists(),
            "Concurrent transactions committed a cross-tenant grant.",
        )
        self.assertTrue(
            observed_block,
            "PostgreSQL did not confirm the expected blocking relationship.",
        )
        self.assertEqual(grant_result, "grant_committed")
        self.assertEqual(
            reassignment_result,
            "reassignment_integrity_rejected",
        )

        print(
            "PostgreSQL locking regression:",
            grant_result,
            reassignment_result,
            "blocking_confirmed",
        )

    def test_grant_after_uncommitted_reassignment_resolves_safely(self):
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        reassignment_written = Event()
        grant_ready = Event()
        release_reassignment = Event()

        def reassign_dataset():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SET LOCAL lock_timeout = '5s'"
                        )
                        cursor.execute(
                            "SET LOCAL statement_timeout = '8s'"
                        )

                    CorporateDataset.objects.filter(
                        pk=self.dataset.pk
                    ).update(organization=self.org_b)

                    reassignment_written.set()

                    if not release_reassignment.wait(timeout=10):
                        raise RuntimeError(
                            "Reassignment release timed out."
                        )

                return "reassignment_committed"
            finally:
                close_old_connections()

        def issue_grant():
            close_old_connections()
            try:
                if not reassignment_written.wait(timeout=10):
                    raise RuntimeError(
                        "Reassignment did not begin."
                    )

                grant_ready.set()

                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SET LOCAL lock_timeout = '5s'"
                            )
                            cursor.execute(
                                "SET LOCAL statement_timeout = '8s'"
                            )

                        DatasetAccessGrant.objects.create(
                            dataset_id=self.dataset.pk,
                            membership_id=self.membership.pk,
                            granted_by_id=self.owner.pk,
                        )

                    return "grant_committed"
                except IntegrityError:
                    return "grant_integrity_rejected"
                except DatabaseError as exc:
                    sqlstate = getattr(
                        getattr(exc, "__cause__", None),
                        "sqlstate",
                        None,
                    )
                    if sqlstate in {"55P03", "57014"}:
                        return f"grant_timeout:{sqlstate}"
                    raise
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            reassignment_future = executor.submit(reassign_dataset)
            grant_future = executor.submit(issue_grant)

            try:
                if not grant_ready.wait(timeout=10):
                    raise RuntimeError(
                        "Grant operation did not become ready."
                    )
            finally:
                release_reassignment.set()

            reassignment_result = reassignment_future.result(timeout=20)
            grant_result = grant_future.result(timeout=20)

        self.dataset.refresh_from_db()

        inconsistent_grants = DatasetAccessGrant.objects.filter(
            dataset=self.dataset
        ).exclude(
            membership__organization=self.dataset.organization
        )

        self.assertFalse(
            inconsistent_grants.exists(),
            "Concurrent transactions committed a cross-tenant grant.",
        )

        self.assertEqual(
            reassignment_result,
            "reassignment_committed",
        )

        self.assertEqual(
            grant_result,
            "grant_integrity_rejected",
            "Grant must be rejected after dataset reassignment.",
        )

        print(
            "PostgreSQL transaction completion results:",
            reassignment_result,
            grant_result,
        )

    def test_uncommitted_reassignment_cannot_create_cross_tenant_grant(self):
        from threading import Barrier
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        synchronization = Barrier(2)
        grant_statement_finished = Event()
        release_reassignment = Event()

        def reassign_dataset():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SET LOCAL lock_timeout = '5s'"
                        )
                        cursor.execute(
                            "SET LOCAL statement_timeout = '8s'"
                        )

                    CorporateDataset.objects.filter(
                        pk=self.dataset.pk
                    ).update(organization=self.org_b)

                    synchronization.wait(timeout=10)

                    if not release_reassignment.wait(timeout=10):
                        raise RuntimeError(
                            "Reassignment transaction release timed out."
                        )

                return "reassignment_committed"
            finally:
                close_old_connections()

        def issue_grant():
            close_old_connections()
            try:
                synchronization.wait(timeout=10)

                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SET LOCAL lock_timeout = '5s'"
                            )
                            cursor.execute(
                                "SET LOCAL statement_timeout = '8s'"
                            )

                        DatasetAccessGrant.objects.create(
                            dataset_id=self.dataset.pk,
                            membership_id=self.membership.pk,
                            granted_by_id=self.owner.pk,
                        )

                    return "grant_committed"
                except IntegrityError:
                    return "grant_integrity_rejected"
                except DatabaseError as exc:
                    sqlstate = getattr(
                        getattr(exc, "__cause__", None),
                        "sqlstate",
                        None,
                    )
                    if sqlstate in {"55P03", "57014"}:
                        return f"grant_lock_or_statement_timeout:{sqlstate}"
                    raise
                finally:
                    grant_statement_finished.set()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            reassignment_future = executor.submit(reassign_dataset)
            grant_future = executor.submit(issue_grant)

            try:
                grant_result = grant_future.result(timeout=10)
            finally:
                release_reassignment.set()

            reassignment_result = reassignment_future.result(timeout=10)

        self.dataset.refresh_from_db()

        inconsistent_grants = DatasetAccessGrant.objects.filter(
            dataset=self.dataset
        ).exclude(
            membership__organization=self.dataset.organization
        )

        self.assertFalse(
            inconsistent_grants.exists(),
            "Concurrent operations created a cross-tenant grant.",
        )

        self.assertIn(
            grant_result,
            {
                "grant_integrity_rejected",
                "grant_lock_or_statement_timeout:55P03",
                "grant_lock_or_statement_timeout:57014",
            },
            "Unexpected grant transaction outcome.",
        )

        print(
            "Uncommitted reassignment concurrency results:",
            reassignment_result,
            grant_result,
        )

    def test_dataset_reassignment_during_grant_creation(self):
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        reassignment_written = Event()
        grant_attempt_started = Event()

        def reassign_dataset():
            close_old_connections()
            try:
                with transaction.atomic():
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SET LOCAL statement_timeout = '8s'")
                    CorporateDataset.objects.filter(
                        pk=self.dataset.pk
                    ).update(organization=self.org_b)

                    reassignment_written.set()

                    if not grant_attempt_started.wait(timeout=10):
                        raise RuntimeError(
                            "Grant transaction did not begin."
                        )

                return "reassignment_committed"
            finally:
                close_old_connections()

        def issue_grant():
            close_old_connections()
            try:
                if not reassignment_written.wait(timeout=10):
                    raise RuntimeError(
                        "Reassignment transaction did not begin."
                    )

                grant_attempt_started.set()

                try:
                    with transaction.atomic():
                        from django.db import connection
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '5s'")
                            cursor.execute("SET LOCAL statement_timeout = '8s'")
                        DatasetAccessGrant.objects.create(
                            dataset_id=self.dataset.pk,
                            membership_id=self.membership.pk,
                            granted_by_id=self.owner.pk,
                        )

                    return "grant_committed"
                except IntegrityError:
                    return "grant_blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            reassignment_future = executor.submit(reassign_dataset)
            grant_future = executor.submit(issue_grant)

            reassignment_result = reassignment_future.result(timeout=20)
            grant_result = grant_future.result(timeout=20)

        self.dataset.refresh_from_db()

        inconsistent_grants = DatasetAccessGrant.objects.filter(
            dataset=self.dataset
        ).exclude(
            membership__organization=self.dataset.organization
        )

        self.assertFalse(
            inconsistent_grants.exists(),
            "Concurrent operations created a cross-tenant grant.",
        )

        print(
            "Reverse-order PostgreSQL concurrency results:",
            reassignment_result,
            grant_result,
        )

    def test_grant_creation_during_dataset_reassignment(self):
        from django.db import connection

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")

        grant_created = Event()
        reassignment_attempted = Event()

        def issue_grant():
            close_old_connections()
            try:
                with transaction.atomic():
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SET LOCAL statement_timeout = '8s'")
                    DatasetAccessGrant.objects.create(
                        dataset_id=self.dataset.pk,
                        membership_id=self.membership.pk,
                        granted_by_id=self.owner.pk,
                    )
                    grant_created.set()

                    if not reassignment_attempted.wait(timeout=10):
                        raise RuntimeError(
                            "Reassignment did not begin."
                        )

                return "grant_committed"
            finally:
                close_old_connections()

        def reassign_dataset():
            close_old_connections()
            try:
                if not grant_created.wait(timeout=10):
                    raise RuntimeError(
                        "Grant transaction did not begin."
                    )

                reassignment_attempted.set()

                try:
                    with transaction.atomic():
                        from django.db import connection
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '5s'")
                            cursor.execute("SET LOCAL statement_timeout = '8s'")
                        CorporateDataset.objects.filter(
                            pk=self.dataset.pk
                        ).update(organization=self.org_b)

                    return "reassignment_committed"
                except IntegrityError:
                    return "reassignment_blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            grant_future = executor.submit(issue_grant)
            reassignment_future = executor.submit(reassign_dataset)

            grant_result = grant_future.result(timeout=20)
            reassignment_result = reassignment_future.result(timeout=20)

        self.dataset.refresh_from_db()

        inconsistent_grants = DatasetAccessGrant.objects.filter(
            dataset=self.dataset
        ).exclude(
            membership__organization=self.dataset.organization
        )

        self.assertFalse(
            inconsistent_grants.exists(),
            "Concurrent transactions created a cross-tenant grant.",
        )

        print(
            "PostgreSQL tenant concurrency results:",
            grant_result,
            reassignment_result,
        )
