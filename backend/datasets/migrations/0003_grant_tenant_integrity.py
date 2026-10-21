"""Enforce dataset-grant tenant consistency in SQLite.

This migration is SQLite-specific. A future PostgreSQL deployment
will require an equivalent, explicitly reviewed integrity design.
"""

from django.db import migrations


TRIGGERS = {
    "grant_tenant_insert": """
        CREATE TRIGGER grant_tenant_insert
        BEFORE INSERT ON datasets_datasetaccessgrant
        FOR EACH ROW
        WHEN (
            SELECT organization_id
            FROM datasets_corporatedataset
            WHERE id = NEW.dataset_id
        ) IS NOT (
            SELECT organization_id
            FROM organizations_organizationmembership
            WHERE id = NEW.membership_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'Grant organization mismatch');
        END;
    """,
    "grant_tenant_update": """
        CREATE TRIGGER grant_tenant_update
        BEFORE UPDATE OF dataset_id, membership_id
        ON datasets_datasetaccessgrant
        FOR EACH ROW
        WHEN (
            SELECT organization_id
            FROM datasets_corporatedataset
            WHERE id = NEW.dataset_id
        ) IS NOT (
            SELECT organization_id
            FROM organizations_organizationmembership
            WHERE id = NEW.membership_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'Grant organization mismatch');
        END;
    """,
    "grant_dataset_org_update": """
        CREATE TRIGGER grant_dataset_org_update
        BEFORE UPDATE OF organization_id
        ON datasets_corporatedataset
        FOR EACH ROW
        WHEN EXISTS (
            SELECT 1
            FROM datasets_datasetaccessgrant AS g
            JOIN organizations_organizationmembership AS m
              ON g.membership_id = m.id
            WHERE g.dataset_id = OLD.id
              AND m.organization_id IS NOT NEW.organization_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'Dataset organization conflicts with grant');
        END;
    """,
    "grant_membership_org_update": """
        CREATE TRIGGER grant_membership_org_update
        BEFORE UPDATE OF organization_id
        ON organizations_organizationmembership
        FOR EACH ROW
        WHEN EXISTS (
            SELECT 1
            FROM datasets_datasetaccessgrant AS g
            JOIN datasets_corporatedataset AS d
              ON g.dataset_id = d.id
            WHERE g.membership_id = OLD.id
              AND d.organization_id IS NOT NEW.organization_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'Membership organization conflicts with grant');
        END;
    """,
}


def install_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        raise RuntimeError(
            "Tenant-integrity triggers require SQLite."
        )

    for sql in TRIGGERS.values():
        schema_editor.execute(sql)


def remove_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        raise RuntimeError(
            "Tenant-integrity triggers require SQLite."
        )

    for name in reversed(tuple(TRIGGERS)):
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0002_datasetaccessgrant"),
    ]

    operations = [
        migrations.RunPython(
            install_triggers,
            reverse_code=remove_triggers,
        ),
    ]
