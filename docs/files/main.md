# `main.py`

**Rol:** Orquestación

Punto de entrada y orquestador del flujo target-only de post-deploy.

## Responsabilidad dentro de la aplicación

Coordina el orden completo del post-deploy. No contiene la lógica detallada de cada remediación; delega en los módulos especializados y mantiene el orden funcional requerido.

## Dependencias

- `argparse`
- `pathlib:Path`
- `truststore`
- `auth:get_access_token`
- `config:load_config`
- `diagnostics:start_diagnostics`
- `powerbi_gateway:bind_semantic_models_to_gateway`
- `semantic_refresh:refresh_semantic_models`
- `http_clients:ApiClient`
- `paginated:remediate_paginated_reports`
- `powerbi_paginated:bind_paginated_reports_to_semantic_models`
- `remediation:apply_remediation, summarize_discovery`
- `workspace:discover_paginated_report_definitions, discover_report_definitions, list_fabric_workspace_items`

## Clases

Este módulo no define clases.

## Funciones de módulo

| Función | Firma |
|---|---|
| `build_parser` | `build_parser()` |
| `_section` | `_section(title: str)` |
| `main` | `main()` |
| `_main` | `_main(args, diagnostics)` |

## Algoritmo / pseudocódigo

```text
INICIO
    cargar configuración
    iniciar diagnóstico
    obtener token Fabric y Power BI
    descubrir objetos del workspace destino
    leer definiciones de Reports y Paginated Reports
    bind Semantic Models -> Gateway
    refresh Semantic Models
    remediar RDL paginados in-place
    redescubrir workspace
    bind runtime Paginated Reports -> Semantic Models
    redescubrir RDL Visuals
    corregir itemId/workspaceId de RDL Visuals
FIN
```

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | `--config` |
| Salida | workspace remediado + logs |

## Relación con otros módulos

**Importa módulos internos:** [`auth.py`](auth.md), [`config.py`](config.md), [`diagnostics.py`](diagnostics.md), [`http_clients.py`](http_clients.md), [`paginated.py`](paginated.md), [`powerbi_gateway.py`](powerbi_gateway.md), [`powerbi_paginated.py`](powerbi_paginated.md), [`remediation.py`](remediation.md), [`semantic_refresh.py`](semantic_refresh.md), [`workspace.py`](workspace.md)

**Es utilizado por:** ningún otro módulo Python detectado de forma directa.

## Código fuente analizado

Archivo: `src/main.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
