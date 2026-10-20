from pathlib import Path

from civiclens.cli import main
from civiclens.models import ImportBundle


def test_csv_converter_produces_valid_source_linked_bundle(capsys):
    fixture = Path(__file__).parents[1] / "examples" / "agenda.csv"
    assert (
        main(
            [
                "convert-csv",
                str(fixture),
                "--meeting-id",
                "sample",
                "--date",
                "2026-10-14",
                "--body",
                "City Council",
                "--title",
                "Sample session",
                "--jurisdiction",
                "Sample City",
                "--source-url",
                "https://example.invalid/meeting",
                "--demo",
            ]
        )
        == 0
    )
    bundle = ImportBundle.model_validate_json(capsys.readouterr().out)
    assert bundle.items[0].meeting_id == bundle.meetings[0].id
    assert bundle.meetings[0].is_demo is True


def test_invalid_input_reports_error_without_database_write(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing.json")]) == 2
    assert capsys.readouterr().err
