"""Correct PostgreSQL tenant-locking UUID variable types."""

from django.db import migrations


CORRECTED_FUNCTION = "\nCREATE OR REPLACE FUNCTION check_grant_tenant()\nRETURNS trigger AS $$\nDECLARE\n    dataset_organization_id uuid;\n    membership_organization_id uuid;\nBEGIN\n    SELECT organization_id\n    INTO dataset_organization_id\n    FROM datasets_corporatedataset\n    WHERE id = NEW.dataset_id\n    FOR SHARE;\n\n    SELECT organization_id\n    INTO membership_organization_id\n    FROM organizations_organizationmembership\n    WHERE id = NEW.membership_id\n    FOR SHARE;\n\n    IF dataset_organization_id IS DISTINCT FROM membership_organization_id\n    THEN\n        RAISE EXCEPTION 'Grant organization mismatch'\n            USING ERRCODE = '23514';\n    END IF;\n\n    RETURN NEW;\nEND;\n$$ LANGUAGE plpgsql;\n"


def apply_fix(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CORRECTED_FUNCTION)


PREVIOUS_FUNCTION = "\nCREATE OR REPLACE FUNCTION check_grant_tenant()\nRETURNS trigger AS $$\nDECLARE\n    dataset_organization_id uuid;\n    membership_organization_id uuid;\nBEGIN\n    SELECT organization_id\n    INTO dataset_organization_id\n    FROM datasets_corporatedataset\n    WHERE id = NEW.dataset_id\n    FOR SHARE;\n\n    SELECT organization_id\n    INTO membership_organization_id\n    FROM organizations_organizationmembership\n    WHERE id = NEW.membership_id\n    FOR SHARE;\n\n    IF dataset_organization_id IS DISTINCT FROM membership_organization_id\n    THEN\n        RAISE EXCEPTION 'Grant organization mismatch'\n            USING ERRCODE = '23514';\n    END IF;\n\n    RETURN NEW;\nEND;\n$$ LANGUAGE plpgsql;\n"

def reverse_fix(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(PREVIOUS_FUNCTION)


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0005_postgresql_grant_row_locking"),
    ]

    operations = [
        migrations.RunPython(
            apply_fix,
            reverse_code=reverse_fix,
        ),
    ]
