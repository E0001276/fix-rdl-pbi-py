# `workspace.py`

Documentación del módulo Python [`src/workspace.py`](../../src/workspace.py).

## Responsabilidad del módulo

Descubre items Fabric y gestiona lectura/actualización de sus definiciones.

## Dependencias

- `base64`
- `json`
- `xml.etree.ElementTree`
- `dataclasses: dataclass, field`
- `pathlib: PurePosixPath`

## Clases

### `WorkspaceItem`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `id` | `str` | `Requerido` |
| `name` | `str` | `Requerido` |
| `kind` | `str` | `Requerido` |
| `folder_id` | `str` | `''` |

### `WorkspaceRdlVisual`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `report_id` | `str` | `Requerido` |
| `report_name` | `str` | `Requerido` |
| `report_folder_id` | `str` | `Requerido` |
| `page_name` | `str` | `Requerido` |
| `definition_part_path` | `str` | `Requerido` |
| `old_item_id` | `str` | `Requerido` |
| `old_workspace_id` | `str` | `Requerido` |
| `parameter_names` | `set[str]` | `field(default_factory=set)` |

### `PaginatedReportInfo`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `item` | `WorkspaceItem` | `Requerido` |
| `parameter_names` | `set[str]` | `field(default_factory=set)` |

### `WorkspaceItems`

#### `reports(self)`

Devuelve los items del workspace cuyo tipo es Report.

**Retorno**

Devuelve valor calculado.

#### `semantic_models(self)`

Devuelve los items del workspace cuyo tipo es SemanticModel.

**Retorno**

Devuelve valor calculado.

#### `paginated_reports(self)`

Devuelve los items del workspace cuyo tipo es PaginatedReport.

**Retorno**

Devuelve valor calculado.

## Funciones

### `_list_all(client, path: str)`

Obtiene todos los elementos de una colección Fabric siguiendo continuation URI/token.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `path` | `str` | `Requerido` |

**Retorno**

Devuelve valor `items`.

**Comportamiento y efectos**

Llamadas relevantes: `client.get`, `print`.
Escribe información de diagnóstico en consola.

### `_print_item(item: WorkspaceItem)`

Imprime información resumida de un item del workspace.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `item` | `WorkspaceItem` | `Requerido` |

**Retorno**

`None`

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `list_fabric_workspace_items(client, workspace_id: str)`

Enumera Reports, Semantic Models y Paginated Reports del workspace destino.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |

**Retorno**

Devuelve valor `items`.

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/{endpoint}'`
- `workspaces/`
Escribe información de diagnóstico en consola.

### `_decode_part(part)`

Decodifica el payload InlineBase64 de una parte de definición Fabric.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `part` | `No especificado` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada, valor `payload`.

**Comportamiento y efectos**

Llamadas relevantes: `base64.b64decode`.

### `_get_definition(client, workspace_id: str, item: WorkspaceItem)`

Solicita la definición Fabric de un item y resuelve respuestas síncronas o LRO.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `item` | `WorkspaceItem` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `client.post`, `client.get_json_lro_result`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/reports/{item.id}/getDefinition'`
- `workspaces/`
- `f'workspaces/{workspace_id}/paginatedReports/{item.id}/getDefinition'`

**Excepciones explícitas**

- `ValueError(f'Definitions are not loaded for item type {item.kind}.')`

### `_literal_value(node)`

Extrae de forma segura el valor de una expresión `Literal` de un JSON de Power BI.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `node` | `No especificado` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada, str.

### `_rdl_visual_parameter_names(visual)`

Obtiene los nombres de parámetros configurados en un RDL Visual.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `visual` | `No especificado` | `Requerido` |

**Retorno**

Devuelve valor `result`.

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`.

### `discover_report_definitions(client, workspace_id: str, workspace_items)`

Lee definiciones de Reports y descubre todos los RDL Visuals presentes.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |

**Retorno**

Devuelve valor `visuals`.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `json.loads`.
Escribe información de diagnóstico en consola.

### `_xml_local_name(tag: str)`

Obtiene el nombre local de una etiqueta XML ignorando el namespace.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `tag` | `str` | `Requerido` |

**Retorno**

`str`

### `_rdl_parameter_names(xml_text: str)`

Extrae los nombres de parámetros declarados en un documento RDL.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |

**Retorno**

Devuelve valor `result`.

### `discover_paginated_report_definitions(client, workspace_id: str, workspace_items)`

Lee definiciones de informes paginados y construye metadatos utilizados para resolverlos.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |

**Retorno**

Devuelve valor `result`.

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `get_report_definition(client, workspace_id: str, report_id: str)`

Obtiene la definición Fabric de un Report específico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `client.post`, `client.get_json_lro_result`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/reports/{report_id}/getDefinition'`
- `workspaces/`

### `get_paginated_report_definition(client, workspace_id: str, report_id: str)`

Obtiene la definición Fabric de un Paginated Report específico sin forzar formato explícito.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `client.post`, `client.get_json_lro_result`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/paginatedReports/{report_id}/getDefinition'`
- `workspaces/`

### `update_report_definition(client, workspace_id: str, report_id: str, definition: dict)`

Actualiza in-place la definición Fabric de un Report.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |
| `definition` | `dict` | `Requerido` |

**Retorno**

Devuelve valor `status_code`.

**Comportamiento y efectos**

Llamadas relevantes: `client.post`, `client.wait_for_lro_completion`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/reports/{report_id}/updateDefinition'`
- `workspaces/`

### `update_paginated_report_definition(client, workspace_id: str, report_id: str, definition: dict)`

Actualiza in-place la definición Fabric de un Paginated Report.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `report_id` | `str` | `Requerido` |
| `definition` | `dict` | `Requerido` |

**Retorno**

Devuelve valor `status_code`.

**Comportamiento y efectos**

Llamadas relevantes: `client.post`, `client.wait_for_lro_completion`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{workspace_id}/paginatedReports/{report_id}/updateDefinition'`
- `workspaces/`

## Archivo fuente

Ruta: `src/workspace.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
