import json
import zipfile
from pathlib import Path

from win_automator.debug_capture import ACTIVE_MARKER, DebugSession, DebugSink
from win_automator.models import Selector, Step, ValueSpec


def test_debug_sink_redacts_field_values(tmp_path: Path):
    (tmp_path / ACTIVE_MARKER).write_text("active", encoding="utf-8")
    sink = DebugSink(tmp_path, source="test", include_values=False)
    step = Step(
        action="set_value",
        target=Selector(control_type="Edit", name="Иванов Иван Иванович", automation_id="txtFullName"),
        value=ValueSpec(source="literal", literal="секретное значение"),
    )
    sink.record_semantic_step(step)
    raw = sink.events_path.read_text(encoding="utf-8")
    assert "Иванов Иван Иванович" not in raw
    assert "секретное значение" not in raw
    assert "<redacted>" in raw
    event = json.loads(raw.strip())
    assert event["type"] == "semantic_step"


def test_debug_sink_from_environment(monkeypatch, tmp_path: Path):
    (tmp_path / ACTIVE_MARKER).write_text("active", encoding="utf-8")
    monkeypatch.setenv("WIN_AUTOMATOR_DEBUG_DIR", str(tmp_path))
    monkeypatch.setenv("WIN_AUTOMATOR_DEBUG_VALUES", "0")
    sink = DebugSink.from_environment("executor")
    assert sink is not None
    sink.log("hello", value_length=5)
    assert sink.events_path.exists()


def test_debug_session_exports_self_contained_zip(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    session = DebugSession()
    (session.root / ACTIVE_MARKER).write_text(session.session_id, encoding="utf-8")
    (session.root / "metadata.json").write_text("{}", encoding="utf-8")
    session.log("problem_marker", note="reproduced")
    package = session.stop({"problem_description": "test"}, cleanup_raw=True)
    assert package.exists()
    assert not session.root.exists()
    with zipfile.ZipFile(str(package), "r") as archive:
        names = set(archive.namelist())
        assert "SUMMARY.md" in names
        assert "manifest.json" in names
        assert "context-final.json" in names
        assert any(name.startswith("events-controller-") for name in names)
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["files"]
