# partial-deploy — описание MCP-сервера

**Каталог:** корень клонированного репозитория `partial-deploy`  
**Идентификатор в Cursor:** `partial-deploy`  
**Транспорт:** stdio (Python + FastMCP)

## Назначение

MCP помогает готовить **частичную выкладку** конфигурации 1С по **плану разработки**:

- копирует только нужные файлы из полной выгрузки на диске;
- складывает их в подпапку пакета (имя задаётся в плане, по умолчанию `config`);
- формирует `partial-deploy-list.txt` для `-listFile`;
- кладёт `deploy-partial.cmd`, README и manifest;
- опционально собирает zip;
- генерирует `deploy-local.cmd.example` с подключением к ИБ (SQL-сервер или файловая база).

Перед вызовом инструментов с подключением агент должен **уточнить у оператора**: тип ИБ, адрес/имя базы, логин, пароль (если есть).

## Установка

```bat
cd partial-deploy
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Запуск вручную: `run_server.cmd` или  
`.venv\Scripts\python.exe server.py`

### Подключение в Cursor (`mcp.json`)

```json
"partial-deploy": {
  "command": "C:\\path\\to\\partial-deploy\\.venv\\Scripts\\python.exe",
  "args": ["C:\\path\\to\\partial-deploy\\server.py"],
  "description": "Частичный деплой 1С: пакет по плану, профиль IB, deploy-partial.cmd"
}
```

## Инструменты MCP

| Инструмент | Что делает |
|------------|------------|
| `list_deploy_plans` | Список встроенных планов (`plans\*.json`) |
| `get_deploy_plan` | Описание плана и полный список файлов |
| `build_partial_deploy_pack` | Сборка каталога пакета (+ zip) из `source_configuration_path` |
| `create_connection_profile` | `deploy-local.cmd.example` (и опционально `deploy-local.cmd`) |
| `run_partial_deploy` | Запуск `deploy-partial.cmd`; **только** `confirm=YES` |

### `build_partial_deploy_pack` — источник списка файлов

Один из вариантов:

- `plan_id` — например `example-minimal`;
- `custom_plan_path` — свой JSON с полем `files`;
- `file_paths` — массив путей относительно корня выгрузки на диске.

### `create_connection_profile` — подключение

| `connection_type` | Что задать |
|-------------------|------------|
| `server` | `server_name` + `infobase_name` или полная `ib_connection_string` (`Srvr="...";Ref="...";`) |
| `file` | `file_infobase_path` или `ib_connection_string` (`File="...";`) |

В `deploy-local.cmd` попадают `SRV` и `REF` либо `FILE_IB` — без кавычек. Кавычки для `/IBConnectionString` добавляет `deploy-partial.cmd`. Обязательно: `user`. Опционально: `password`, `platform_path`, `log_dir`, `also_write_local_cmd`.

### `run_partial_deploy`

Реально вызывает Designer. В каталоге пакета должны быть `deploy-partial.cmd` и `deploy-local.cmd`. Инструмент передаёт `CONFIRM=YES` и не ждёт повторный ввод. Без явного согласия пользователя не вызывать.

## Тестовые планы (`plans\*.json`)

В репозитории лежат **учебные** планы с вымышленными путями — для демонстрации формата и проверки сборки. Для продакшена скопируйте JSON и укажите реальные пути из вашей выгрузки.

| Файл | `plan_id` | Зачем |
|------|-----------|-------|
| `example-minimal.json` | `example-minimal` | Минимум: один справочник, `config_root_folder`: `config` |
| `example-custom-root.json` | `example-custom-root` | Другое имя папки в пакете: `minimal-cf` |

```json
{
  "id": "example-minimal",
  "title": "Тест: один объект конфигурации",
  "description": "Учебный план; пути вымышленные",
  "config_root_folder": "config",
  "include_configuration_xml": true,
  "files": [
    "Catalogs/DemoСправочник.xml",
    "Catalogs/DemoСправочник/Ext/ManagerModule.bsl"
  ]
}
```

Поля:

- **`config_root_folder`** — подпапка внутри собранного пакета (не имя каталога на вашем диске). По умолчанию в коде — `config`. `create_connection_profile` читает её из `plan.json` и пишет `SRC=%~dp0<папка>`.
- **`include_configuration_xml`** — копирует `Configuration.xml` и ставит её первой строкой `partial-deploy-list.txt`. Без этой строки конфигуратор не загрузит корень конфигурации.
- **`files`** — пути от корня **источника** `source_configuration_path`, слэши `/`.

## Состав пакета после сборки

```
<output_directory>\
  <config_root_folder>\           … минимальная копия выгрузки
  partial-deploy-list.txt         … для Designer -listFile
  deploy-partial.cmd              … запуск загрузки (подтверждение YES)
  deploy-local.cmd.example        … создаётся через create_connection_profile
  README-partial-deploy.txt
  manifest-config-files.txt
  plan.json                       … снимок плана
  <имя>.zip                       … если create_zip=true
```

Загрузка (платформа 8.5):  
`/LoadConfigFromFiles` + `-listFile` + `-partial` + `-updateConfigDumpInfo` + `/UpdateDBCfg Dynamic+` через `/IBConnectionString`.

Успех: `deploy-partial-result.txt` содержит `0`.

## Файлы каталога deploy

| Файл | Назначение |
|------|------------|
| `server.py` | MCP-сервер |
| `pack_builder.py` | Логика сборки |
| `plans\` | Тестовые и пользовательские планы |
| `templates\deploy-partial.cmd` | Шаблон батника |
| `requirements.txt` | Зависимости Python |
| `run_server.cmd` | Запуск |
| `README.md` | Краткая памятка |
| `DESCRIPTION.md` | Этот файл |

## Безопасность

- `deploy-local.cmd` с паролем и адресом прода **не коммитить**.
- `run_partial_deploy` только после явного подтверждения оператора.
- На проде закрыть лишние сеансы конфигуратора с целевой ИБ.