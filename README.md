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
  "description": "Частичный деплой 1С: пакет по плану, SRV/REF или FILE_IB, запуск cmd"
}
```

## Инструменты

| Tool | Назначение |
|------|------------|
| `list_deploy_plans` | Встроенные планы (`plans/*.json`) |
| `get_deploy_plan` | Файлы и описание плана |
| `build_partial_deploy_pack` | Собрать папку выгрузки, список, `deploy-partial.cmd`, README, zip |
| `create_connection_profile` | `deploy-local.cmd.example` (server/file, логин, пароль) |
| `run_partial_deploy` | Запуск `deploy-partial.cmd`, только `confirm=YES` |

Перед `create_connection_profile` и `run_partial_deploy` агент должен уточнить у пользователя:

- **connection_type**: `server` или `file`
- для **server**: `server_name`, `infobase_name` (или полная `ib_connection_string`)
- для **file**: `file_infobase_path`
- **user**, при необходимости **password**, **platform_path**

## Тестовые планы (`plans/`)

В репозитории только **учебные** JSON — пути вымышленные, подставьте свою выгрузку или скопируйте план под задачу.

| `plan_id` | Назначение |
|-----------|------------|
| `example-minimal` | Один справочник, папка в пакете `config\` |
| `example-custom-root` | Несколько объектов, папка в пакете `minimal-cf\` |

Образец своего плана:

```json
{
  "id": "my-plan",
  "title": "Моя выкладка",
  "config_root_folder": "config",
  "include_configuration_xml": true,
  "files": ["Catalogs/МойСправочник.xml"]
}
```

- **`config_root_folder`** — имя подпапки **внутри пакета** (по умолчанию `config`). `create_connection_profile` сам пишет этот путь в `SRC`.
- **`include_configuration_xml`** — добавляет `Configuration.xml` в список загрузки.
- Пути в **`files`** — от **корня выгрузки на диске** (где лежит `Configuration.xml`), слэши `/`.

## Свой plan.json из OpenSpec / плана в Cursor

Сохраните список файлов в JSON и передайте в `build_partial_deploy_pack` как `custom_plan_path`.