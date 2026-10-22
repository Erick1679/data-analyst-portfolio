"""Lock referenced tenant records during PostgreSQL grant validation."""

from django.db import migrations


LOCKED_GRANT_FUNCTION = """
CREATE OR REPLACE FUNCTION check_grant_tenant()
RETURNS trigger AS $$
DECLARE
    dataset_organization_id uuid;
    membership_organization_id uuid;
BEGIN
    SELECT organization_id
    INTO dataset_organization_id
    FROM datasets_corporatedataset
    WHERE id = NEW.dataset_id
    FOR SHARE;

    SELECT organization_id
    INTO membership_organization_id
    FROM organizations_organizationmembership
    WHERE id = NEW.membership_id
    FOR SHARE;

    IF dataset_organization_id IS DISTINCT FROM membership_organization_id
    THEN
        RAISE EXCEPTION 'Grant organization mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


UNLOCKED_GRANT_FUNCTION = """
CREATE OR REPLACE FUNCTION check_grant_tenant()
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
        RAISE EXCEPTION 'Grant organization mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def install_locking(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(LOCKED_GRANT_FUNCTION)


def remove_locking(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(UNLOCKED_GRANT_FUNCTION)


class Migration(migrations.Migration):

    dependencies = [
        (
            "datasets",
            "0004_postgresql_grant_integrity_sqlstate",
        ),
    ]

    operations = [
        migrations.RunPython(
            install_locking,
            reverse_code=remove_locking,
        ),
    ]
