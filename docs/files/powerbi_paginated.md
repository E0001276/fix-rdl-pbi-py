# `powerbi_paginated.py`

Documentación del módulo Python [`src/powerbi_paginated.py`](../../src/powerbi_paginated.py).

## Responsabilidad del módulo

Corrige el datasource runtime de los informes paginados para apuntar al Semantic Model destino.

## Dependencias

- `paginated: _extract_rdl_binding, _find_rdl_part, _decode_part, _resolve_semantic_model`
- `workspace: get_paginated_report_definition`

## Funciones

### `_norm(value)`

Normaliza un valor textual para comparaciones tolerantes a mayúsculas/minúsculas y espacios.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

`str`

### `_datasources(payload: dict)`

Extrae la lista `value` de un payload de datasources de Power BI.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `payload` | `dict` | `Requerido` |

**Retorno**

`list[dict]`

### `_connection_details(datasource: dict)`

Obtiene de forma segura el diccionario `connectionDetails` de un datasource.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `datasource` | `dict` | `Requerido` |

**Retorno**

`dict`

### `_runtime_name(datasource: dict)`

Obtiene el nombre runtime del datasource del informe paginado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `datasource` | `dict` | `Requerido` |

**Retorno**

`str`

### `_target_database(semantic_model_id: str)`

Construye el nombre de base virtual `sobe_wowvirtualserver-{semanticModelId}`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `semantic_model_id` | `str` | `Requerido` |

**Retorno**

`str`

### `get_paginated_report_datasources(powerbi, workspace_id: str, report_id: str)`

Consulta los datasources runtime actuales de un informe paginado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |

**Retorno**

`list[dict]`

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/reports/{report_id}/datasources'`
- `groups/`

### `_get_persisted_rdl_datasource_names(fabric, workspace_id: str, report_id: str)`

Lee la definición persistida del RDL y obtiene sus nombres de datasource.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |

**Retorno**

`list[str]`

### `_find_runtime_for_rdl(runtime_datasources: list[dict], rdl_name: str)`

Relaciona un datasource persistido en RDL con el datasource runtime correspondiente.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `runtime_datasources` | `list[dict]` | `Requerido` |
| `rdl_name` | `str` | `Requerido` |

**Retorno**

Devuelve valor calculado.

### `_build_update_details(runtime_datasources: list[dict], rdl_names: list[str], semantic_model_id: str)`

Construye la colección `updateDetails` requerida por `Default.UpdateDatasources`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `runtime_datasources` | `list[dict]` | `Requerido` |
| `rdl_names` | `list[str]` | `Requerido` |
| `semantic_model_id` | `str` | `Requerido` |

**Retorno**

Devuelve valor `details`.

### `bind_paginated_reports_to_semantic_models(powerbi, fabric, workspace_items, paginated_infos, config)`

Mirror the proven .NET paginated runtime remediation, target-only.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `fabric` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `paginated_infos` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve lista, valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `powerbi.post`.
Rutas/API construidas o utilizadas:
- `Mirror the proven .NET paginated runtime remediation, target-only.

    The target semantic model is resolved from the target workspace folder.
    The persisted target RDL supplies datasourceName. Power BI GET /datasources
    supplies the current server. Only the virtual database semantic-model ID is
    replaced. TakeOver is executed before Default.UpdateDatasources, exactly as
    in the working .NET application.
    `
- `  Calling Default.TakeOver...`
- `f'groups/{config.workspace_id}/reports/{item.id}/Default.TakeOver'`
- `  Calling Default.UpdateDatasources...`
- `f'groups/{config.workspace_id}/reports/{item.id}/Default.UpdateDatasources'`
- `groups/`
- `/Default.TakeOver`
- `/Default.UpdateDatasources`
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError(f'Unable to safely bind {len(failures)} paginated report runtime datasource(s).')`

## Archivo fuente

Ruta: `src/powerbi_paginated.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
