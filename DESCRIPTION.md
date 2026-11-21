# partial-deploy — описание MCP-сервера

**Каталог:** корень клонированного репозитория `partial-deploy`  
**Идентификатор в Cursor:** `partial-deploy`  
**Транспорт:** stdio (Python + FastMCP)

## Назначение

MCP помогает готовить **частичную выкладку** конфигурации 1С по **плану разработки**:

- копирует только нужные файлы из выгрузки (`Тип\` или другой корень);
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

- `plan_id` — например `ekruly-v7`;
- `custom_plan_path` — свой JSON с полем `files`;
- `file_paths` — массив путей относительно корня выгрузки.

### `create_connection_profile` — подключение

| `connection_type` | Что задать |
|-------------------|------------|
| `server` | `server_name` + `infobase_name` или полная `ib_connection_string` (`Srvr="...";Ref="...";`) |
| `file` | `file_infobase_path` или `ib_connection_string` (`File="...";`) |

Обязательно: `user`. Опционально: `password`, `platform_path`, `log_dir`, `also_write_local_cmd`.

### `run_partial_deploy`

Реально вызывает Designer. В каталоге пакета должны быть `deploy-partial.cmd` и `deploy-local.cmd`. Без явного согласия пользователя не вызывать.

## Формат плана (`plans\*.json`)

```json
{
  "id": "ekruly-v7",
  "title": "Экрулы по ТЗ v7",
  "description": "…",
  "config_root_folder": "Тип",
  "include_configuration_xml": true,
  "files": [
    "InformationRegisters/….xml",
    "CommonModules/…/Ext/Module.bsl"
  ]
}
```

Пути — **от корня выгрузки**, прямые слэши `/`.

Встроенный план: **`ekruly-v7`** (доработка экрулов ТЗ v7, 19 объектных путей + `Configuration.xml`).

## Состав пакета после сборки

```
<output_directory>\
  Тип\                          … минимальная выгрузка
  partial-deploy-list.txt       … для Designer -listFile
  deploy-partial.cmd              … запуск загрузки (подтверждение YES)
  deploy-local.cmd.example        … создаётся через create_connection_profile
  README-partial-deploy.txt
  manifest-config-files.txt
  plan.json                       … снимок плана
  <имя>.zip                       … если create_zip=true
```

Загрузка (как в проекте Просто):  
`/LoadConfigFromFiles` + `-listFile` + `-partial` + `-updateConfigDumpInfo` + `/UpdateDBCfg Dynamic+` через `/IBConnectionString`.

Успех: `deploy-partial-result.txt` содержит `0`.

## Файлы каталога deploy

| Файл | Назначение |
|------|------------|
| `server.py` | MCP-сервер |
| `pack_builder.py` | Логика сборки |
| `plans\` | Планы выкладки |
| `templates\deploy-partial.cmd` | Шаблон батника |
| `requirements.txt` | Зависимости Python |
| `run_server.cmd` | Запуск |
| `README.md` | Краткая памятка |
| `DESCRIPTION.md` | Этот файл |

## Безопасность

- `deploy-local.cmd` с паролем и адресом прода **не коммитить**.
- `run_partial_deploy` только после явного подтверждения оператора.
- На проде закрыть лишние сеансы конфигуратора с целевой ИБ.

## Связанные артефакты проекта Просто

- Готовый пакет для прода: `partial-deploy-prod\ekruly-v7\`
- Список для тестовой ИБ: `load-tip-kz-list.txt` (корень репозитория)
- Частичная выкладка в файловую «База ТИП»: `deploy-tip-partial.ps1`