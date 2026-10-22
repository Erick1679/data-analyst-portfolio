"""Enforce dataset-grant tenant consistency in SQLite and PostgreSQL."""

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



POSTGRESQL_FUNCTIONS = {
    "check_grant_tenant": """
        CREATE FUNCTION check_grant_tenant()
        RETURNS trigger AS $$
        BEGIN
            IF (
                SELECT organization_id
                FROM datasets_corporatedataset
                WHERE id = NEW.dataset_id
            ) IS DISTINCT FROM (
                SELECT organization_id
                FROM organizations_organizationmembership
                WHERE id = NEW.membership_id
            ) THEN
                RAISE EXCEPTION 'Grant organization mismatch' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """,
    "check_dataset_grant_tenant": """
        CREATE FUNCTION check_dataset_grant_tenant()
        RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM datasets_datasetaccessgrant AS g
                JOIN organizations_organizationmembership AS m
                  ON g.membership_id = m.id
                WHERE g.dataset_id = OLD.id
                  AND m.organization_id IS DISTINCT FROM NEW.organization_id
            ) THEN
                RAISE EXCEPTION 'Dataset organization conflicts with grant' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """,
    "check_membership_grant_tenant": """
        CREATE FUNCTION check_membership_grant_tenant()
        RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM datasets_datasetaccessgrant AS g
                JOIN datasets_corporatedataset AS d
                  ON g.dataset_id = d.id
                WHERE g.membership_id = OLD.id
                  AND d.organization_id IS DISTINCT FROM NEW.organization_id
            ) THEN
                RAISE EXCEPTION 'Membership organization conflicts with grant' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """,
}

POSTGRESQL_TRIGGERS = {
    "grant_tenant_insert": """
        CREATE TRIGGER grant_tenant_insert
        BEFORE INSERT ON datasets_datasetaccessgrant
        FOR EACH ROW
        EXECUTE FUNCTION check_grant_tenant();
    """,
    "grant_tenant_update": """
        CREATE TRIGGER grant_tenant_update
        BEFORE UPDATE OF dataset_id, membership_id
        ON datasets_datasetaccessgrant
        FOR EACH ROW
        EXECUTE FUNCTION check_grant_tenant();
    """,
    "grant_dataset_org_update": """
        CREATE TRIGGER grant_dataset_org_update
        BEFORE UPDATE OF organization_id
        ON datasets_corporatedataset
        FOR EACH ROW
        EXECUTE FUNCTION check_dataset_grant_tenant();
    """,
    "grant_membership_org_update": """
        CREATE TRIGGER grant_membership_org_update
        BEFORE UPDATE OF organization_id
        ON organizations_organizationmembership
        FOR EACH ROW
        EXECUTE FUNCTION check_membership_grant_tenant();
    """,
}

def install_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for sql in TRIGGERS.values():
            schema_editor.execute(sql)
    elif vendor == "postgresql":
        for sql in POSTGRESQL_FUNCTIONS.values():
            schema_editor.execute(sql)
        for sql in POSTGRESQL_TRIGGERS.values():
            schema_editor.execute(sql)
    else:
        raise RuntimeError(
            f"Unsupported tenant-integrity database: {vendor}"
        )


def remove_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in reversed(tuple(TRIGGERS)):
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )
    elif vendor == "postgresql":
        trigger_tables = {
            "grant_tenant_insert": "datasets_datasetaccessgrant",
            "grant_tenant_update": "datasets_datasetaccessgrant",
            "grant_dataset_org_update": "datasets_corporatedataset",
            "grant_membership_org_update":
                "organizations_organizationmembership",
        }

        for name, table in reversed(tuple(trigger_tables.items())):
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name} ON {table}"
            )

        for name in reversed(tuple(POSTGRESQL_FUNCTIONS)):
            schema_editor.execute(
                f"DROP FUNCTION IF EXISTS {name}()"
            )
    else:
        raise RuntimeError(
            f"Unsupported tenant-integrity database: {vendor}"
        )


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
