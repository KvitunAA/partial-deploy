# partial-deploy (MCP)

Формирование пакета частичной выкладки 1С по плану разработки и командных файлов загрузки.

Полное описание: **[DESCRIPTION.md](DESCRIPTION.md)**.

## Установка

```bat
cd partial-deploy
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Cursor (`mcp.json`)

```json
"partial-deploy": {
  "command": "C:\\path\\to\\partial-deploy\\.venv\\Scripts\\python.exe",
  "args": ["C:\\path\\to\\partial-deploy\\server.py"],
  "description": "Частичный деплой 1С: пакет по плану, IB_CONN, запуск cmd"
}
```

## Инструменты

| Tool | Назначение |
|------|------------|
| `list_deploy_plans` | Встроенные планы (`plans/*.json`) |
| `get_deploy_plan` | Файлы и описание плана |
| `build_partial_deploy_pack` | Собрать `Тип\`, список, `deploy-partial.cmd`, README, zip |
| `create_connection_profile` | `deploy-local.cmd.example` (server/file, логин, пароль) |
| `run_partial_deploy` | Запуск `deploy-partial.cmd`, только `confirm=YES` |

Перед `create_connection_profile` и `run_partial_deploy` агент должен уточнить у пользователя:

- **connection_type**: `server` или `file`
- для **server**: `server_name`, `infobase_name` (или полная `ib_connection_string`)
- для **file**: `file_infobase_path`
- **user**, при необходимости **password**, **platform_path**

## Планы

Добавляйте JSON в `plans/`, образец — `ekruly-v7.json`:

```json
{
  "id": "my-plan",
  "title": "…",
  "config_root_folder": "Тип",
  "include_configuration_xml": true,
  "files": ["Catalogs/…"]
}
```

## Свой plan.json из OpenSpec / плана в Cursor

Сохраните список файлов в JSON и передайте в `build_partial_deploy_pack` как `custom_plan_path`.