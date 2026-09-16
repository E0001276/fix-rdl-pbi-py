# `remediation.py`

**Rol:** Remediación de RDL Visuals

Resolución de Paginated Reports y corrección de `itemId`/`workspaceId` en los RDL Visuals.

## Responsabilidad dentro de la aplicación

Relaciona cada RDL Visual con el Paginated Report correcto y actualiza la definición del Report principal únicamente cuando la resolución es segura.

## Dependencias

- `base64`
- `json`
- `re`
- `unicodedata`
- `workspace:get_report_definition, update_report_definition`

## Clases

Este módulo no define clases.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_plain` | `_plain(value: str)` |
| `_tokens` | `_tokens(value: str, drop_generic: bool=False)` |
| `_strip_report_prefix` | `_strip_report_prefix(candidate_name: str, report_name: str)` |
| `_folder_candidates` | `_folder_candidates(paginated_infos, visual)` |
| `_resolve_by_page_label` | `_resolve_by_page_label(candidates, visual)` |
| `_resolve_by_parameters` | `_resolve_by_parameters(candidates, visual)` |
| `_resolve_paginated` | `_resolve_paginated(paginated_infos, visual)` |
| `summarize_discovery` | `summarize_discovery(workspace_items, rdl_visuals, config)` |
| `_print_resolution_header` | `_print_resolution_header(index, total, visual)` |
| `_encode_json_part` | `_encode_json_part(data: dict)` |
| `_set_literal_value` | `_set_literal_value(node: dict, value: str)` |
| `_patch_rdl_visual_part` | `_patch_rdl_visual_part(part: dict, target_item_id: str, target_workspace_id: str)` |
| `_read_reference_from_definition` | `_read_reference_from_definition(definition_response: dict, part_path: str)` |
| `apply_remediation` | `apply_remediation(fabric, rdl_visuals, paginated_infos, workspace_items, config)` |

## Algoritmo / pseudocódigo

```text
PARA CADA RDL Visual
    obtener candidatos de la misma carpeta
    intentar resolver por etiqueta de página
    si hace falta, resolver por parámetros
    exigir una única resolución segura
    leer definición actual del Report
    modificar visual.json:
        itemId <- paginatedReportId destino
        workspaceId <- workspace destino
    updateDefinition del Report
    verificar referencia persistida
FIN PARA
```

## APIs relacionadas

- `POST /v1/workspaces/{workspaceId}/reports/{reportId}/getDefinition`
- `POST /v1/workspaces/{workspaceId}/reports/{reportId}/updateDefinition`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | RDL Visuals + paginated_infos + workspace_items |
| Salida | visual.json con itemId/workspaceId destino |

## Relación con otros módulos

**Importa módulos internos:** [`workspace.py`](workspace.md)

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/remediation.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
