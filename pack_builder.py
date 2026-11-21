"""Сборка каталога частичной выкладки 1С: файлы Тип + список + cmd + README."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path
from typing import Any


def _deploy_root() -> Path:
    return Path(__file__).resolve().parent


def plans_dir() -> Path:
    return _deploy_root() / "plans"


def list_plans() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(plans_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        result.append(
            {
                "id": data.get("id", path.stem),
                "title": data.get("title", path.stem),
                "description": data.get("description", ""),
                "file_count": len(data.get("files") or []),
                "path": str(path),
            }
        )
    return result


def load_plan(plan_id: str) -> dict[str, Any]:
    path = plans_dir() / f"{plan_id}.json"
    if not path.is_file():
        alt = next(plans_dir().glob(f"{plan_id}*.json"), None)
        if alt is None:
            raise FileNotFoundError(f"План не найден: {plan_id}")
        path = alt
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_file_list(
    plan_id: str | None,
    file_paths: list[str] | None,
    custom_plan_path: str | None,
) -> tuple[list[str], dict[str, Any]]:
    meta: dict[str, Any] = {"id": "custom", "title": "Пользовательский список"}
    if custom_plan_path:
        data = json.loads(Path(custom_plan_path).read_text(encoding="utf-8"))
        meta = data
        files = list(data.get("files") or [])
    elif plan_id:
        data = load_plan(plan_id)
        meta = data
        files = list(data.get("files") or [])
    elif file_paths:
        files = list(file_paths)
    else:
        raise ValueError("Укажите plan_id, custom_plan_path или file_paths")

    normalized: list[str] = []
    for item in files:
        line = item.strip().replace("\\", "/")
        if line:
            normalized.append(line)
    return normalized, meta


def build_ib_connection_string(
    connection_type: str,
    server_name: str | None,
    infobase_name: str | None,
    ib_connection_string: str | None,
    file_infobase_path: str | None,
) -> str:
    ct = connection_type.strip().lower()
    if ib_connection_string and ib_connection_string.strip():
        return ib_connection_string.strip()
    if ct == "server":
        if not server_name or not infobase_name:
            raise ValueError(
                "Для server нужны server_name и infobase_name (или полная ib_connection_string)"
            )
        return f'Srvr="{server_name}";Ref="{infobase_name}";'
    if ct == "file":
        if not file_infobase_path:
            raise ValueError("Для file нужен file_infobase_path или ib_connection_string")
        # File= для /IBConnectionString (как в staged-скриптах проекта)
        p = file_infobase_path.replace("/", "\\")
        return f'File="{p}";'
    raise ValueError('connection_type должен быть "server" или "file"')


def write_local_cmd_example(
    output_dir: Path,
    connection_type: str,
    user: str,
    password: str | None,
    platform_path: str | None,
    server_name: str | None,
    infobase_name: str | None,
    ib_connection_string: str | None,
    file_infobase_path: str | None,
    src_hint: str | None,
    log_dir: str | None,
) -> Path:
    ib = build_ib_connection_string(
        connection_type,
        server_name,
        infobase_name,
        ib_connection_string,
        file_infobase_path,
    )
    platform = platform_path or r"C:\Program Files\1cv8\8.5.1.1522\bin\1cv8.exe"
    log = log_dir or r"C:\temp\1c-partial-deploy"
    src = src_hint or r"%~dp0Тип"

    lines = [
        "@echo off",
        "REM Скопируйте в deploy-local.cmd (не коммитить).",
        f'set "PLATFORM={platform}"',
        f'set "SRC={src}"',
        f'set "LOGDIR={log}"',
        f'set "USER={user}"',
    ]
    if password:
        lines.append(f'set "PASS={password}"')
    else:
        lines.append("REM Пароль не задан — строку PASS не раскрывать")

    if connection_type.lower() == "server":
        lines.append(f'set "IB_CONN={ib}"')
        if server_name and infobase_name and not ib_connection_string:
            lines.append(f'REM Альтернатива: set "SRV={server_name}" / set "REF={infobase_name}"')
    else:
        lines.append(f'set "IB_CONN={ib}"')
        if file_infobase_path:
            lines.append(f'REM Файловая ИБ: {file_infobase_path}')

    text = "\r\n".join(lines) + "\r\n"
    target = output_dir / "deploy-local.cmd.example"
    target.write_text(text, encoding="utf-8")
    return target


def _copy_runner(output_dir: Path) -> Path:
    template = _deploy_root() / "templates" / "deploy-partial.cmd"
    dest = output_dir / "deploy-partial.cmd"
    shutil.copyfile(template, dest)
    return dest


def _write_readme(output_dir: Path, title: str, plan_id: str) -> Path:
    readme = output_dir / "README-partial-deploy.txt"
    today = date.today().strftime("%d.%m.%Y")
    text = f"""Частичная выкладка 1С — {title}
План: {plan_id}
Дата сборки: {today}

1) deploy-local.cmd.example → deploy-local.cmd (IB_CONN или файл, USER, при необходимости PASS).
2) deploy-partial.cmd — запуск (подтверждение YES).
3) Папка Тип\\ — минимальная выгрузка.
4) partial-deploy-list.txt — список для -listFile.

Платформа 8.5: /IBConnectionString, -partial, -updateConfigDumpInfo, /UpdateDBCfg Dynamic+.
Успех: deploy-partial-result.txt содержит 0.
"""
    readme.write_text(text, encoding="utf-8")
    return readme


def build_pack(
    source_configuration_path: str,
    output_directory: str,
    plan_id: str | None = None,
    file_paths: list[str] | None = None,
    custom_plan_path: str | None = None,
    pack_title: str | None = None,
    create_zip: bool = True,
) -> dict[str, Any]:
    src_root = Path(source_configuration_path)
    if not (src_root / "Configuration.xml").is_file():
        raise FileNotFoundError(
            f"Нет Configuration.xml в корне выгрузки: {src_root}"
        )

    files, meta = resolve_file_list(plan_id, file_paths, custom_plan_path)
    root_name = meta.get("config_root_folder", "Тип")
    title = pack_title or meta.get("title") or meta.get("id", "partial")
    pid = meta.get("id", plan_id or "custom")

    out = Path(output_directory)
    if out.exists():
        shutil.rmtree(out)
    tip = out / root_name
    tip.mkdir(parents=True)

    if meta.get("include_configuration_xml", True):
        shutil.copy2(src_root / "Configuration.xml", tip / "Configuration.xml")

    copied: list[str] = []
    for rel in files:
        rel_win = rel.replace("/", "\\")
        src_file = src_root / rel_win
        if not src_file.is_file():
            raise FileNotFoundError(f"Нет файла в источнике: {src_file}")
        dest = tip / rel_win
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
        copied.append(rel)

    list_path = out / "partial-deploy-list.txt"
    list_path.write_text("\n".join(files) + "\n", encoding="utf-8-sig")

    manifest = out / "manifest-config-files.txt"
    manifest_lines = (["Configuration.xml"] if meta.get("include_configuration_xml", True) else []) + files
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    _copy_runner(out)
    _write_readme(out, title, pid)

    plan_snapshot = out / "plan.json"
    plan_snapshot.write_text(
        json.dumps({**meta, "files": files}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    zip_path: str | None = None
    if create_zip:
        zip_file = out.parent / f"{out.name}.zip"
        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in out.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(out.parent))
        zip_path = str(zip_file)

    return {
        "output_directory": str(out),
        "config_folder": str(tip),
        "files_copied": len(copied) + (1 if meta.get("include_configuration_xml", True) else 0),
        "list_file": str(list_path),
        "runner": str(out / "deploy-partial.cmd"),
        "zip": zip_path,
        "plan_id": pid,
        "title": title,
    }