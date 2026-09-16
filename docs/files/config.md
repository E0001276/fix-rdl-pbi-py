# `config.py`

Documentación del módulo Python [`src/config.py`](../../src/config.py).

## Responsabilidad del módulo

Define y carga la configuración funcional del post-deploy.

## Dependencias

- `json`
- `dataclasses: dataclass`
- `pathlib: Path`

## Clases

### `PostDeployConfig`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `workspace_id` | `str` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |
| `expected_oracle_database` | `str` | `Requerido` |
| `fail_on_unresolved_rdl_visual` | `bool` | `Requerido` |
| `apply_rdl_visual_fix` | `bool` | `Requerido` |
| `apply_paginated_report_fix` | `bool` | `Requerido` |
| `fail_on_unresolved_paginated_report` | `bool` | `Requerido` |
| `bind_semantic_models_to_connection` | `bool` | `Requerido` |
| `fail_on_unresolved_connection_binding` | `bool` | `Requerido` |
| `bind_paginated_reports_to_semantic_models` | `bool` | `Requerido` |
| `fail_on_unresolved_paginated_datasource_binding` | `bool` | `Requerido` |
| `recreate_paginated_on_definition_mismatch` | `bool` | `Requerido` |
| `refresh_semantic_models` | `bool` | `Requerido` |
| `wait_for_refresh` | `bool` | `Requerido` |
| `fail_on_refresh_error` | `bool` | `Requerido` |
| `refresh_poll_seconds` | `int` | `Requerido` |
| `refresh_timeout_seconds` | `int` | `Requerido` |

## Funciones

### `load_config(path: str)`

Lee el archivo JSON de configuración y construye una instancia de `PostDeployConfig`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path` | `str` | `Requerido` |

**Retorno**

`PostDeployConfig`

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`, `Path`.

## Archivo fuente

Ruta: `src/config.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
