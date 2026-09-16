# `workspace.py`

**Rol:** Acceso y descubrimiento de objetos Fabric

Descubrimiento de objetos Fabric y lectura/actualización de definiciones de Reports y Paginated Reports.

> **Restricción del tenant:** `getDefinition` de Paginated Reports se invoca sin especificar explícitamente `format=PaginatedReportDefinition`.

## Responsabilidad dentro de la aplicación

Centraliza el inventario de objetos del workspace y el acceso a definiciones Fabric. Es la base del enfoque target-only porque obtiene IDs y definiciones directamente del destino.

## Dependencias

- `base64`
- `json`
- `xml.etree.ElementTree`
- `dataclasses:dataclass, field`
- `pathlib:PurePosixPath`

## Clases

### `WorkspaceItem`

Clase de datos sin métodos explícitos.

### `WorkspaceRdlVisual`

Clase de datos sin métodos explícitos.

### `PaginatedReportInfo`

Clase de datos sin métodos explícitos.

### `WorkspaceItems`

| Método | Firma |
|---|---|
| `reports` | `reports(self)` |
| `semantic_models` | `semantic_models(self)` |
| `paginated_reports` | `paginated_reports(self)` |

## Funciones de módulo

| Función | Firma |
|---|---|
| `_list_all` | `_list_all(client, path: str)` |
| `_print_item` | `_print_item(item: WorkspaceItem)` |
| `list_fabric_workspace_items` | `list_fabric_workspace_items(client, workspace_id: str)` |
| `_decode_part` | `_decode_part(part)` |
| `_get_definition` | `_get_definition(client, workspace_id: str, item: WorkspaceItem)` |
| `_literal_value` | `_literal_value(node)` |
| `_rdl_visual_parameter_names` | `_rdl_visual_parameter_names(visual)` |
| `discover_report_definitions` | `discover_report_definitions(client, workspace_id: str, workspace_items)` |
| `_xml_local_name` | `_xml_local_name(tag: str)` |
| `_rdl_parameter_names` | `_rdl_parameter_names(xml_text: str)` |
| `discover_paginated_report_definitions` | `discover_paginated_report_definitions(client, workspace_id: str, workspace_items)` |
| `get_report_definition` | `get_report_definition(client, workspace_id: str, report_id: str)` |
| `get_paginated_report_definition` | `get_paginated_report_definition(client, workspace_id: str, report_id: str)` |
| `update_report_definition` | `update_report_definition(client, workspace_id: str, report_id: str, definition: dict)` |
| `update_paginated_report_definition` | `update_paginated_report_definition(client, workspace_id: str, report_id: str, definition: dict)` |

## Algoritmo / pseudocódigo

```text
INICIO
    listar Reports, Semantic Models y Paginated Reports
    construir WorkspaceItems
    PARA CADA Report
        getDefinition
        decodificar visual.json
        detectar rdlVisual y parámetros
    FIN PARA
    PARA CADA Paginated Report
        getDefinition
        localizar .rdl
        extraer parámetros
    FIN PARA
    exponer helpers get/updateDefinition
FIN
```

## APIs relacionadas

- `GET /v1/workspaces/{workspaceId}/reports`
- `GET /v1/workspaces/{workspaceId}/semanticModels`
- `GET /v1/workspaces/{workspaceId}/paginatedReports`
- `POST .../getDefinition`
- `POST .../updateDefinition`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | cliente Fabric + workspaceId |
| Salida | inventario, definiciones y objetos de descubrimiento |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md), [`paginated.py`](paginated.md), [`powerbi_paginated.py`](powerbi_paginated.md), [`remediation.py`](remediation.md)

## Código fuente analizado

Archivo: `src/workspace.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
