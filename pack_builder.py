"""Сборка каталога частичной выкладки 1С: минимальная выгрузка + список + cmd + README."""

from __future__ import annotations

import json
import re
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


def _bat_set(name: str, value: str) -> str:
    """Строка set для cmd. Значение без кавычек: их добавляет сам батник при вызове 1cv8."""
    if re.search(r'[\r\n"]', value):
        raise ValueError(f"{name}: кавычки и переводы строк недопустимы")
    return f'set "{name}={value.replace("%", "%%")}"'


def _folder_name(value: str) -> str:
    name = value.strip()
    if not name or name in {".", ".."} or re.search(r'[/\\:"%&<>|?*]', name):
        raise ValueError(f"Недопустимое имя папки пакета: {value}")
    return name


def resolve_connection_parts(
    connection_type: str,
    server_name: str | None,
    infobase_name: str | None,
    ib_connection_string: str | None,
    file_infobase_path: str | None,
) -> dict[str, str]:
    """Части подключения без кавычек: mode=server (server, ref) или mode=file (path)."""
    ct = connection_type.strip().lower()
    if ct not in {"server", "file"}:
        raise ValueError('connection_type должен быть "server" или "file"')

    if ib_connection_string and ib_connection_string.strip():
        raw = ib_connection_string.strip()
        file_match = re.search(r'(?i)(?:^|;)File="([^"]*)"', raw)
        server_match = re.search(r'(?i)(?:^|;)Srvr="([^"]*)"', raw)
        ref_match = re.search(r'(?i)(?:^|;)Ref="([^"]*)"', raw)
        if ct == "file":
            if not file_match:
                raise ValueError('Для file в ib_connection_string нужен File="...";')
            return {"mode": "file", "path": file_match.group(1)}
        if not server_match or not ref_match:
            raise ValueError('Для server в ib_connection_string нужны Srvr="..."; и Ref="...";')
        return {"mode": "server", "server": server_match.group(1), "ref": ref_match.group(1)}

    if ct == "server":
        if not server_name or not infobase_name:
            raise ValueError(
                "Для server нужны server_name и infobase_name (или полная ib_connection_string)"
            )
        return {"mode": "server", "server": server_name, "ref": infobase_name}

    if not file_infobase_path:
        raise ValueError("Для file нужен file_infobase_path или ib_connection_string")
    return {"mode": "file", "path": file_infobase_path.replace("/", "\\")}


def _pack_config_folder(output_dir: Path) -> str:
    plan_path = output_dir / "plan.json"
    if not plan_path.is_file():
        return "config"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    return _folder_name(str(data.get("config_root_folder") or "config"))


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
    parts = resolve_connection_parts(
        connection_type,
        server_name,
        infobase_name,
        ib_connection_string,
        file_infobase_path,
    )
    platform = platform_path or r"C:\Program Files\1cv8\8.5.1.1522\bin\1cv8.exe"
    log = log_dir or r"C:\temp\1c-partial-deploy"
    folder = _pack_config_folder(output_dir)
    src = src_hint or f"%~dp0{folder}"

    lines = [
        "@echo off",
        "REM Скопируйте в deploy-local.cmd (не коммитить).",
        "REM Кавычки в строку подключения подставляет deploy-partial.cmd.",
        "REM Необязательно для серверной базы: RAS, CLUSTER_USER, CLUSTER_PWD, CLUSTER_ID, RAC.",
        _bat_set("PLATFORM", platform),
        f'set "SRC={src}"',
        _bat_set("LOGDIR", log),
        _bat_set("USER", user),
    ]
    if password:
        lines.append(_bat_set("PASS", password))
    else:
        lines.append("REM Пароль не задан — строку PASS не раскрывать")

    if parts["mode"] == "server":
        lines.append(_bat_set("SRV", parts["server"]))
        lines.append(_bat_set("REF", parts["ref"]))
    else:
        lines.append(_bat_set("FILE_IB", parts["path"]))

    text = "\r\n".join(lines) + "\r\n"
    target = output_dir / "deploy-local.cmd.example"
    target.write_text(text, encoding="utf-8")
    return target


def _copy_runner(output_dir: Path) -> Path:
    templates = _deploy_root() / "templates"
    dest = output_dir / "deploy-partial.cmd"
    shutil.copyfile(templates / "deploy-partial.cmd", dest)
    shutil.copyfile(templates / "close-target-sessions.ps1", output_dir / "close-target-sessions.ps1")
    return dest


def _write_readme(
    output_dir: Path, title: str, plan_id: str, config_root_folder: str
) -> Path:
    readme = output_dir / "README-partial-deploy.txt"
    today = date.today().strftime("%d.%m.%Y")
    text = f"""Частичная выкладка 1С — {title}
План: {plan_id}
Дата сборки: {today}

1) deploy-local.cmd.example → deploy-local.cmd (SRV+REF или FILE_IB, USER, при необходимости PASS).
2) deploy-partial.cmd — запуск (подтверждение YES, либо переменная CONFIRM=YES).
3) Папка {config_root_folder}\\ — минимальная выгрузка из плана.
4) partial-deploy-list.txt — список для -listFile, вместе с Configuration.xml, если она включена в план.

Платформа 8.5: /IBConnectionString, -partial, -updateConfigDumpInfo, /UpdateDBCfg Dynamic+ -SessionTerminate force.
Сеансы завершаются и блокируются только у этой базы.
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
    root_name = _folder_name(str(meta.get("config_root_folder") or "config"))
    title = pack_title or meta.get("title") or meta.get("id", "partial")
    pid = meta.get("id", plan_id or "custom")

    out = Path(output_directory)
    if out.exists():
        shutil.rmtree(out)
    pack_config = out / root_name
    pack_config.mkdir(parents=True)

    if meta.get("include_configuration_xml", True):
        shutil.copy2(src_root / "Configuration.xml", pack_config / "Configuration.xml")

    copied: list[str] = []
    for rel in files:
        rel_win = rel.replace("/", "\\")
        src_file = src_root / rel_win
        if not src_file.is_file():
            raise FileNotFoundError(f"Нет файла в источнике: {src_file}")
        dest = pack_config / rel_win
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
        copied.append(rel)

    list_files = list(files)
    if meta.get("include_configuration_xml", True) and "Configuration.xml" not in list_files:
        list_files.insert(0, "Configuration.xml")

    list_path = out / "partial-deploy-list.txt"
    list_path.write_text("\n".join(list_files) + "\n", encoding="utf-8-sig")

    manifest = out / "manifest-config-files.txt"
    manifest_lines = (["Configuration.xml"] if meta.get("include_configuration_xml", True) else []) + files
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    _copy_runner(out)
    _write_readme(out, title, pid, root_name)

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
        "config_folder": str(pack_config),
        "files_copied": len(copied) + (1 if meta.get("include_configuration_xml", True) else 0),
        "list_file": str(list_path),
        "runner": str(out / "deploy-partial.cmd"),
        "zip": zip_path,
        "plan_id": pid,
        "title": title,
    }