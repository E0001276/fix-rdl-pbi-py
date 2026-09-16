# `remediation.py`

Documentación del módulo Python [`src/remediation.py`](../../src/remediation.py).

## Responsabilidad del módulo

Resuelve RDL Visuals contra informes paginados destino y actualiza `itemId`/`workspaceId` en Reports.

## Dependencias

- `base64`
- `json`
- `re`
- `unicodedata`
- `workspace: get_report_definition, update_report_definition`

## Funciones

### `_plain(value: str)`

Normaliza texto removiendo acentos, signos y diferencias de mayúsculas para facilitar comparaciones.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `str` | `Requerido` |

**Retorno**

`str`

### `_tokens(value: str, drop_generic: bool=False)`

Tokeniza y normaliza un texto; opcionalmente elimina palabras genéricas de nombres de página.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `str` | `Requerido` |
| `drop_generic` | `bool` | `False` |

**Retorno**

Devuelve valor calculado.

### `_strip_report_prefix(candidate_name: str, report_name: str)`

Elimina del nombre de un paginado el prefijo que coincide con el nombre del reporte principal.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `candidate_name` | `str` | `Requerido` |
| `report_name` | `str` | `Requerido` |

**Retorno**

`str`

### `_folder_candidates(paginated_infos, visual)`

Prioriza informes paginados ubicados en la misma carpeta que el reporte que contiene el RDL Visual.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `paginated_infos` | `No especificado` | `Requerido` |
| `visual` | `No especificado` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada, valor calculado.

### `_resolve_by_page_label(candidates, visual)`

Intenta resolver un paginado a partir del nombre de la página del reporte.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `candidates` | `No especificado` | `Requerido` |
| `visual` | `No especificado` | `Requerido` |

**Retorno**

Devuelve NoneType, tupla.

### `_resolve_by_parameters(candidates, visual)`

Intenta resolver un paginado comparando parámetros del RDL Visual contra parámetros definidos en el RDL.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `candidates` | `No especificado` | `Requerido` |
| `visual` | `No especificado` | `Requerido` |

**Retorno**

Devuelve NoneType, tupla.

### `_resolve_paginated(paginated_infos, visual)`

Combina las estrategias de resolución para obtener un único informe paginado candidato.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `paginated_infos` | `No especificado` | `Requerido` |
| `visual` | `No especificado` | `Requerido` |

**Retorno**

Devuelve tupla, valor `by_page`, valor `by_parameters`.

### `summarize_discovery(workspace_items, rdl_visuals, config)`

Imprime un resumen de objetos y RDL Visuals descubiertos antes de la remediación.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `workspace_items` | `No especificado` | `Requerido` |
| `rdl_visuals` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `_print_resolution_header(index, total, visual)`

Imprime el encabezado de diagnóstico de un RDL Visual que será resuelto.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `index` | `No especificado` | `Requerido` |
| `total` | `No especificado` | `Requerido` |
| `visual` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `_encode_json_part(data: dict)`

Serializa un JSON y lo codifica en Base64 para una definición Fabric.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `data` | `dict` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `json.dumps`, `base64.b64encode`.

### `_set_literal_value(node: dict, value: str)`

Actualiza el valor de una expresión `Literal` dentro de la estructura del `visual.json`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `node` | `dict` | `Requerido` |
| `value` | `str` | `Requerido` |

**Retorno**

`None`

### `_patch_rdl_visual_part(part: dict, target_item_id: str, target_workspace_id: str)`

Modifica en una parte `visual.json` el `itemId` y `workspaceId` de un RDL Visual.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `part` | `dict` | `Requerido` |
| `target_item_id` | `str` | `Requerido` |
| `target_workspace_id` | `str` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`, `base64.b64decode`.

**Excepciones explícitas**

- `RuntimeError(f"Unsupported payload type for {part.get('path')}: {part.get('payloadType')}")`
- `RuntimeError(f"Definition part is not an RDL visual: {part.get('path')}")`
- `RuntimeError(f"Unable to create RDL visual report reference in {part.get('path')}")`

### `_read_reference_from_definition(definition_response: dict, part_path: str)`

Lee de una definición de reporte los IDs actualmente persistidos para un RDL Visual.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `definition_response` | `dict` | `Requerido` |
| `part_path` | `str` | `Requerido` |

**Retorno**

Devuelve tupla.

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`, `base64.b64decode`.

### `apply_remediation(fabric, rdl_visuals, paginated_infos, workspace_items, config)`

Resuelve cada RDL Visual contra un informe paginado destino y actualiza la definición del reporte.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |
| `rdl_visuals` | `No especificado` | `Requerido` |
| `paginated_infos` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError(f'Unable to resolve {len(unresolved)} RDL Visual relationship(s) safely. No report definitions were updated.')`
- `RuntimeError(f'Definition part not found: {visual.definition_part_path}')`
- `RuntimeError(f'RDL visual update verification failed for {report_name} / {visual.page_name}.')`

## Archivo fuente

Ruta: `src/remediation.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
