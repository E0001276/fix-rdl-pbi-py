# `powerbi_paginated.py`

**Rol:** Binding runtime de paginados

Binding runtime de informes paginados hacia los Semantic Models reales del workspace destino.

## Responsabilidad dentro de la aplicación

Corrige la conexión efectiva que Power BI mantiene para un informe paginado. Esta fase complementa el cambio del XML RDL y opera sobre el datasource runtime del servicio.

## Dependencias

- `paginated:_extract_rdl_binding, _find_rdl_part, _decode_part, _resolve_semantic_model`
- `workspace:get_paginated_report_definition`

## Clases

Este módulo no define clases.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_norm` | `_norm(value)` |
| `_datasources` | `_datasources(payload: dict)` |
| `_connection_details` | `_connection_details(datasource: dict)` |
| `_runtime_name` | `_runtime_name(datasource: dict)` |
| `_target_database` | `_target_database(semantic_model_id: str)` |
| `get_paginated_report_datasources` | `get_paginated_report_datasources(powerbi, workspace_id: str, report_id: str)` |
| `_get_persisted_rdl_datasource_names` | `_get_persisted_rdl_datasource_names(fabric, workspace_id: str, report_id: str)` |
| `_find_runtime_for_rdl` | `_find_runtime_for_rdl(runtime_datasources: list[dict], rdl_name: str)` |
| `_build_update_details` | `_build_update_details(runtime_datasources: list[dict], rdl_names: list[str], semantic_model_id: str)` |
| `bind_paginated_reports_to_semantic_models` | `bind_paginated_reports_to_semantic_models(powerbi, fabric, workspace_items, paginated_infos, config)` |

## Algoritmo / pseudocódigo

```text
PARA CADA Paginated Report
    obtener datasource runtime actual
    leer datasourceName persistido en el RDL
    resolver Semantic Model destino
    conservar connectionDetails.server
    database <- "sobe_wowvirtualserver-" + semanticModelId
    POST Default.TakeOver
    POST Default.UpdateDatasources
    volver a consultar datasources y validar
FIN PARA
```

## APIs relacionadas

- `GET /groups/{workspaceId}/reports/{reportId}/datasources`
- `POST /groups/{workspaceId}/reports/{reportId}/Default.TakeOver`
- `POST /groups/{workspaceId}/reports/{reportId}/Default.UpdateDatasources`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | clientes Power BI/Fabric + paginados + config |
| Salida | datasource runtime apuntando al Semantic Model destino |

## Relación con otros módulos

**Importa módulos internos:** [`paginated.py`](paginated.md), [`workspace.py`](workspace.md)

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/powerbi_paginated.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
