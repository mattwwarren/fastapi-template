from pytest_alembic.runner import MigrationContext


def test_upgrade(alembic_runner: MigrationContext) -> None:
    for head in alembic_runner.heads:
        alembic_runner.migrate_up_to(head)


def test_downgrade(alembic_runner: MigrationContext) -> None:
    for head in alembic_runner.heads:
        alembic_runner.migrate_up_to(head)
        alembic_runner.migrate_down_to("base")
        alembic_runner.migrate_up_to(head)


def test_model_definitions_match_ddl(alembic_runner: MigrationContext) -> None:
    for head in alembic_runner.heads:
        alembic_runner.migrate_up_to(head)
    has_changes = False

    def check_revision(context, revision, directives):
        nonlocal has_changes
        script = directives[0]
        has_changes = not script.upgrade_ops.is_empty()

    alembic_runner.config.alembic_config.attributes["process_revision_directives"] = (
        check_revision
    )
    alembic_runner.generate_revision(autogenerate=True)
    assert not has_changes, "Schema drift detected. Generate a new Alembic migration."
