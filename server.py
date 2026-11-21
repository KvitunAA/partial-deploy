"""MCP-сервер: пакет частичной выкладки 1С и профиль подключения."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Annotated, Any, Literal

try:
    from fastmcp import FastMCP
    from pydantic import Field
except ImportError as exc:
    raise SystemExit(
        "Установите зависимости: pip install -r requirements.txt"
    ) from exc

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pack_builder import (  # noqa: E402
    build_pack,
    list_plans,
    load_plan,
    write_local_cmd_example,
)

APP_NAME = "partial-deploy"
logger = logging.getLogger(APP_NAME)
mcp = FastMCP(APP_NAME)

_CONN = (
    "Способ подключения к ИБ: server — SQL/кластер (Srvr+Ref); "
    "file — файловая ИБ (File=... в IB_CONN). "
    "Если пользователь не указал — спросите до вызова инструмента."
)


@mcp.tool()
def list_deploy_plans() -> str:
    """Список встроенных планов частичной выкладки (JSON в каталоге plans/)."""
    items = list_plans()
    return json.dumps(items, ensure_ascii=False, indent=2)


@mcp.tool()
def get_deploy_plan(
    plan_id: Annotated[str, Field(description="Идентификатор плана, например ekruly-v7")],
) -> str:
    """Полный план: описание и перечень файлов относительно корня выгрузки (Тип/)."""
    data = load_plan(plan_id)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def build_partial_deploy_pack(
    source_configuration_path: Annotated[
        str,
        Field(description="Каталог выгрузки 1С с Configuration.xml (например ...\\Тип)"),
    ],
    output_directory: Annotated[
        str,
        Field(description="Куда собрать пакет (будет создан заново)"),
    ],
    plan_id: Annotated[
        str | None,
        Field(description="ID плана из list_deploy_plans, например ekruly-v7"),
    ] = None,
    file_paths: Annotated[
        list[str] | None,
        Field(description="Свой список путей от корня выгрузки, если plan_id не задан"),
    ] = None,
    custom_plan_path: Annotated[
        str | None,
        Field(description="Путь к своему plan.json вместо встроенного plan_id"),
    ] = None,
    pack_title: Annotated[str | None, Field(description="Заголовок пакета для README")] = None,
    create_zip: Annotated[bool, Field(description="Создать zip рядом с каталогом пакета")] = True,
) -> str:
    """
    Собирает каталог для частичного деплоя: Тип\\, partial-deploy-list.txt,
    deploy-partial.cmd, README, manifest; опционально zip.
    Нужен plan_id или file_paths или custom_plan_path.
    """
    result = build_pack(
        source_configuration_path=source_configuration_path,
        output_directory=output_directory,
        plan_id=plan_id,
        file_paths=file_paths,
        custom_plan_path=custom_plan_path,
        pack_title=pack_title,
        create_zip=create_zip,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def create_connection_profile(
    output_directory: Annotated[
        str,
        Field(description="Каталог пакета частичной выкладки (куда положить deploy-local.cmd.example)"),
    ],
    connection_type: Annotated[
        Literal["server", "file"],
        Field(description=_CONN),
    ],
    user: Annotated[
        str,
        Field(description="Имя пользователя 1С; если неизвестно — спросите у оператора"),
    ],
    password: Annotated[
        str | None,
        Field(description="Пароль; пусто — не записывать PASS в local.cmd"),
    ] = None,
    server_name: Annotated[
        str | None,
        Field(description='Сервер 1С для server, напр. "sql-prod01" или "1c-app:1541"'),
    ] = None,
    infobase_name: Annotated[
        str | None,
        Field(description='Имя ИБ на сервере для server, напр. "tip_prod"'),
    ] = None,
    ib_connection_string: Annotated[
        str | None,
        Field(description='Полная строка IB_CONN, напр. Srvr="...";Ref="...";'),
    ] = None,
    file_infobase_path: Annotated[
        str | None,
        Field(description="Путь к файловой ИБ для connection_type=file"),
    ] = None,
    platform_path: Annotated[
        str | None,
        Field(description="Путь к 1cv8.exe, по умолчанию 8.5.1.1522"),
    ] = None,
    log_dir: Annotated[
        str | None,
        Field(description="Каталог логов Designer (ASCII-путь предпочтителен)"),
    ] = None,
    also_write_local_cmd: Annotated[
        bool,
        Field(description="Сразу записать deploy-local.cmd (не только .example)"),
    ] = False,
) -> str:
    """
    Формирует deploy-local.cmd.example с IB_CONN, USER, PLATFORM.
    Для прода на SQL: connection_type=server, server_name + infobase_name.
    Для файловой ИБ: connection_type=file + file_infobase_path.
    Обязательные поля, если не заданы заранее, уточняйте у пользователя.
    """
    out = output_directory
    path = write_local_cmd_example(
        output_dir=__import__("pathlib").Path(out),
        connection_type=connection_type,
        user=user,
        password=password,
        platform_path=platform_path,
        server_name=server_name,
        infobase_name=infobase_name,
        ib_connection_string=ib_connection_string,
        file_infobase_path=file_infobase_path,
        src_hint=None,
        log_dir=log_dir,
    )
    written = [str(path)]
    if also_write_local_cmd:
        dest = path.parent / "deploy-local.cmd"
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(str(dest))
    conn_preview = {
        "connection_type": connection_type,
        "user": user,
        "has_password": bool(password),
        "files": written,
    }
    return json.dumps(conn_preview, ensure_ascii=False, indent=2)


@mcp.tool()
def run_partial_deploy(
    pack_directory: Annotated[str, Field(description="Каталог с deploy-partial.cmd и deploy-local.cmd")],
    confirm: Annotated[
        Literal["YES"],
        Field(description='Обязательно "YES" после явного согласия оператора'),
    ],
) -> str:
    """
    Запускает deploy-partial.cmd (реальная загрузка в ИБ). Только с confirm=YES.
    Требует готовый deploy-local.cmd в pack_directory.
    """
    if confirm != "YES":
        return json.dumps({"error": "confirm должен быть YES"}, ensure_ascii=False)
    cmd = os.path.join(pack_directory, "deploy-partial.cmd")
    if not os.path.isfile(cmd):
        return json.dumps({"error": f"Нет {cmd}"}, ensure_ascii=False)
    logger.info("Запуск частичной выкладки: %s", cmd)
    proc = subprocess.run(
        ["cmd", "/c", cmd],
        cwd=pack_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.dumps(
        {
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()