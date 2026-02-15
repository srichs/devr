"""Virtual environment helper behavior tests."""

from pathlib import Path

from devr import venv


def test_is_inside_venv_false_when_prefix_matches(monkeypatch) -> None:
    monkeypatch.setattr(venv.sys, "prefix", "/usr")
    monkeypatch.setattr(venv.sys, "base_prefix", "/usr")

    assert venv.is_inside_venv() is False


def test_is_inside_venv_true_when_prefix_differs(monkeypatch) -> None:
    monkeypatch.setattr(venv.sys, "prefix", "/tmp/.venv")
    monkeypatch.setattr(venv.sys, "base_prefix", "/usr")

    assert venv.is_inside_venv() is True


def test_venv_python_posix_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(venv.os, "name", "posix")

    assert venv.venv_python(tmp_path) == tmp_path / "bin" / "python"


def test_venv_python_windows_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(venv.os, "name", "nt")

    assert venv.venv_python(tmp_path) == tmp_path / "Scripts" / "python.exe"


def test_find_venv_prefers_configured_path(tmp_path: Path) -> None:
    configured = tmp_path / "custom-venv" / "bin"
    configured.mkdir(parents=True)
    (configured / "python").write_text("", encoding="utf-8")

    resolved = venv.find_venv(tmp_path, "custom-venv")

    assert resolved == (tmp_path / "custom-venv").resolve()


def test_find_venv_uses_active_venv_when_configured_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(venv, "is_inside_venv", lambda: True)
    monkeypatch.setattr(venv.sys, "prefix", str(tmp_path / ".active-venv"))

    resolved = venv.find_venv(tmp_path, "missing")

    assert resolved == Path(venv.sys.prefix)


def test_find_venv_falls_back_to_default_names(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(venv, "is_inside_venv", lambda: False)
    path = tmp_path / "venv" / "bin"
    path.mkdir(parents=True)
    (path / "python").write_text("", encoding="utf-8")

    resolved = venv.find_venv(tmp_path, None)

    assert resolved == (tmp_path / "venv").resolve()


def test_find_venv_returns_none_when_not_found(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(venv, "is_inside_venv", lambda: False)

    assert venv.find_venv(tmp_path, None) is None


def test_create_venv_uses_configured_python(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _check_call(args: list[str]) -> None:
        calls.append(args)

    monkeypatch.setattr(venv.subprocess, "check_call", _check_call)

    target = tmp_path / "nested" / ".venv"
    venv.create_venv(tmp_path, target, python_exe="python3.12")

    assert target.parent.exists()
    assert calls == [["python3.12", "-m", "venv", str(target)]]


def test_create_venv_uses_current_interpreter_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(venv.sys, "executable", "/usr/bin/python-test")
    monkeypatch.setattr(venv.subprocess, "check_call", lambda args: calls.append(args))

    target = tmp_path / ".venv"
    venv.create_venv(tmp_path, target)

    assert calls == [["/usr/bin/python-test", "-m", "venv", str(target)]]


def test_run_py_calls_subprocess_with_venv_python(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []
    venv_dir = tmp_path / ".venv"

    monkeypatch.setattr(venv, "venv_python", lambda _: Path("/tmp/python"))
    monkeypatch.setattr(
        venv.subprocess,
        "call",
        lambda args, cwd: calls.append((args, cwd)) or 7,
    )

    code = venv.run_py(venv_dir, ["-V"], cwd=tmp_path)

    assert code == 7
    assert calls == [(["/tmp/python", "-V"], str(tmp_path))]


def test_run_module_wraps_run_py(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, list[str], Path]] = []

    def _run_py(venv_dir: Path, args: list[str], cwd: Path) -> int:
        calls.append((venv_dir, args, cwd))
        return 0

    monkeypatch.setattr(venv, "run_py", _run_py)

    code = venv.run_module(tmp_path / ".venv", "ruff", ["check", "."], cwd=tmp_path)

    assert code == 0
    assert calls == [(tmp_path / ".venv", ["-m", "ruff", "check", "."], tmp_path)]
