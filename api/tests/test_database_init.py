from unittest.mock import MagicMock

import app.database as database


def _configure_init_db(monkeypatch, table_names, columns=()):
    inspector = MagicMock()
    inspector.get_table_names.return_value = table_names
    inspector.get_columns.return_value = columns
    monkeypatch.setattr(database, 'inspect', lambda _: inspector)

    create_all = MagicMock()
    monkeypatch.setattr(database.Base.metadata, 'create_all', create_all)
    monkeypatch.setattr(database, 'engine', MagicMock())
    monkeypatch.setattr(database, 'database_exists', lambda _: True)
    monkeypatch.setattr(database, 'create_database', MagicMock())
    monkeypatch.setattr(database.alembic_command, 'stamp', MagicMock())
    monkeypatch.setattr(database.alembic_command, 'upgrade', MagicMock())
    return create_all


def test_init_db_upgrades_versioned_database(monkeypatch):
    create_all = _configure_init_db(monkeypatch, ['alembic_version'])

    database.init_db()

    database.alembic_command.upgrade.assert_called_once()
    database.alembic_command.stamp.assert_not_called()
    create_all.assert_called_once()


def test_init_db_upgrades_legacy_unversioned_database(monkeypatch):
    create_all = _configure_init_db(
        monkeypatch,
        ['underlying_communication_service'],
        [{'name': 'underlying_communication_service_name'}],
    )

    database.init_db()

    database.alembic_command.stamp.assert_called_once()
    assert database.alembic_command.stamp.call_args.args[1] == 'base'
    database.alembic_command.upgrade.assert_called_once()
    create_all.assert_called_once()


def test_init_db_stamps_current_unversioned_database(monkeypatch):
    create_all = _configure_init_db(
        monkeypatch,
        ['underlying_communication_service'],
        [
            {'name': 'underlying_communication_service_name'},
            {'name': 'underlying_communication_service_abbreviation'},
        ],
    )

    database.init_db()

    database.alembic_command.upgrade.assert_not_called()
    database.alembic_command.stamp.assert_called_once()
    assert database.alembic_command.stamp.call_args.args[1] == 'head'
    create_all.assert_called_once()
