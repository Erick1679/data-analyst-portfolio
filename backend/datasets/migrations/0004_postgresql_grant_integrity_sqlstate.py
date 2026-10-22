"""Classify PostgreSQL tenant-integrity violations correctly."""


from django.db import migrations


POSTGRESQL_FUNCTIONS = {'check_grant_tenant': '\n'
                       '        CREATE FUNCTION check_grant_tenant()\n'
                       '        RETURNS trigger AS $$\n'
                       '        BEGIN\n'
                       '            IF (\n'
                       '                SELECT organization_id\n'
                       '                FROM datasets_corporatedataset\n'
                       '                WHERE id = NEW.dataset_id\n'
                       '            ) IS DISTINCT FROM (\n'
                       '                SELECT organization_id\n'
                       '                FROM organizations_organizationmembership\n'
                       '                WHERE id = NEW.membership_id\n'
                       '            ) THEN\n'
                       "                RAISE EXCEPTION 'Grant organization mismatch' "
                       "USING ERRCODE = '23514';\n"
                       '            END IF;\n'
                       '            RETURN NEW;\n'
                       '        END;\n'
                       '        $$ LANGUAGE plpgsql;\n'
                       '    ',
 'check_dataset_grant_tenant': '\n'
                               '        CREATE FUNCTION check_dataset_grant_tenant()\n'
                               '        RETURNS trigger AS $$\n'
                               '        BEGIN\n'
                               '            IF EXISTS (\n'
                               '                SELECT 1\n'
                               '                FROM datasets_datasetaccessgrant AS g\n'
                               '                JOIN '
                               'organizations_organizationmembership AS m\n'
                               '                  ON g.membership_id = m.id\n'
                               '                WHERE g.dataset_id = OLD.id\n'
                               '                  AND m.organization_id IS DISTINCT '
                               'FROM NEW.organization_id\n'
                               '            ) THEN\n'
                               "                RAISE EXCEPTION 'Dataset organization "
                               "conflicts with grant' USING ERRCODE = '23514';\n"
                               '            END IF;\n'
                               '            RETURN NEW;\n'
                               '        END;\n'
                               '        $$ LANGUAGE plpgsql;\n'
                               '    ',
 'check_membership_grant_tenant': '\n'
                                  '        CREATE FUNCTION '
                                  'check_membership_grant_tenant()\n'
                                  '        RETURNS trigger AS $$\n'
                                  '        BEGIN\n'
                                  '            IF EXISTS (\n'
                                  '                SELECT 1\n'
                                  '                FROM datasets_datasetaccessgrant AS '
                                  'g\n'
                                  '                JOIN datasets_corporatedataset AS '
                                  'd\n'
                                  '                  ON g.dataset_id = d.id\n'
                                  '                WHERE g.membership_id = OLD.id\n'
                                  '                  AND d.organization_id IS DISTINCT '
                                  'FROM NEW.organization_id\n'
                                  '            ) THEN\n'
                                  "                RAISE EXCEPTION 'Membership "
                                  "organization conflicts with grant' USING ERRCODE = "
                                  "'23514';\n"
                                  '            END IF;\n'
                                  '            RETURN NEW;\n'
                                  '        END;\n'
                                  '        $$ LANGUAGE plpgsql;\n'
                                  '    '}


def update_postgresql_functions(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    for sql in POSTGRESQL_FUNCTIONS.values():
        schema_editor.execute(
            sql.replace(
                "CREATE FUNCTION",
                "CREATE OR REPLACE FUNCTION",
                1,
            )
        )


def restore_previous_functions(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    for sql in POSTGRESQL_FUNCTIONS.values():
        original_sql = sql.replace(
            " USING ERRCODE = '23514'",
            "",
        )

        schema_editor.execute(
            original_sql.replace(
                "CREATE FUNCTION",
                "CREATE OR REPLACE FUNCTION",
                1,
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0003_grant_tenant_integrity"),
    ]

    operations = [
        migrations.RunPython(
            update_postgresql_functions,
            reverse_code=restore_previous_functions,
        ),
    ]
