# `paginated.py`

**Rol:** Remediación de definición RDL

Corrección in-place del XML RDL de los informes paginados, preservando su `itemId`.

> **Restricción crítica:** el flujo actualiza el mismo Paginated Report. No debe usar una estrategia create/delete/rename porque cambiaría el `itemId` y afectaría Git Integration.

## Responsabilidad dentro de la aplicación

Corrige referencias persistidas en el RDL sin reemplazar el objeto Fabric. La modificación se hace de forma text-preserving para minimizar cambios ajenos al binding.

## Dependencias

- `base64`
- `re`
- `xml.etree.ElementTree`
- `dataclasses:dataclass`
- `workspace:get_paginated_report_definition, update_paginated_report_definition`

## Clases

### `PaginatedBindingResult`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_local_name` | `_local_name(tag: str)` |
| `_normalize_workspace_datasource_prefix` | `_normalize_workspace_datasource_prefix(workspace_name: str)` |
| `_target_datasource_name` | `_target_datasource_name(current_name: str, workspace_name: str)` |
| `_decode_part` | `_decode_part(part: dict)` |
| `_encode_rdl` | `_encode_rdl(xml_text: str)` |
| `_validate_rdl_namespace` | `_validate_rdl_namespace(xml_text: str)` |
| `_replace_tag_text` | `_replace_tag_text(xml_text: str, tag_name: str, transform)` |
| `_replace_datasource_names` | `_replace_datasource_names(xml_text: str, workspace_name: str)` |
| `_find_rdl_part` | `_find_rdl_part(definition_response: dict)` |
| `_extract_rdl_binding` | `_extract_rdl_binding(xml_text: str)` |
| `_resolve_semantic_model` | `_resolve_semantic_model(workspace_items, paginated_item)` |
| `_update_connect_string` | `_update_connect_string(value: str, target_model_id: str)` |
| `_patch_rdl` | `_patch_rdl(xml_text: str, workspace_name: str, semantic_model_id: str, semantic_model_name: str)` |
| `_is_binding_logically_correct` | `_is_binding_logically_correct(binding: dict, workspace_name: str, semantic_model_name: str)` |
| `_build_fabric_definition` | `_build_fabric_definition(original_response: dict, item_name: str, xml_after: str)` |
| `_expected_datasource_name` | `_expected_datasource_name(workspace_name: str, semantic_model_name: str)` |
| `_binding_matches_target` | `_binding_matches_target(binding: dict, workspace_name: str, model_name: str)` |
| `_extract_created_item_id` | `_extract_created_item_id(client, response)` |
| `remediate_paginated_reports` | `remediate_paginated_reports(fabric, workspace_items, paginated_infos, config)` |

## Algoritmo / pseudocódigo

```text
PARA CADA Paginated Report
    localizar parte .rdl de la definición
    decodificar InlineBase64
    extraer binding actual
    resolver Semantic Model destino de la misma carpeta
    calcular datasourceName esperado
    actualizar PowerBIWorkspaceName
    actualizar PowerBIDatasetName
    actualizar connect string con semanticModelId
    validar XML y binding lógico
    SI hubo cambios
        updateDefinition sobre el mismo itemId
    FIN SI
FIN PARA
```

## APIs relacionadas

- `POST /v1/workspaces/{workspaceId}/paginatedReports/{id}/getDefinition`
- `POST /v1/workspaces/{workspaceId}/paginatedReports/{id}/updateDefinition`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | definiciones RDL + workspace_items + config |
| Salida | RDL actualizado sobre el mismo itemId |

## Relación con otros módulos

**Importa módulos internos:** [`workspace.py`](workspace.md)

**Es utilizado por:** [`main.py`](main.md), [`powerbi_paginated.py`](powerbi_paginated.md)

## Código fuente analizado

Archivo: `src/paginated.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
