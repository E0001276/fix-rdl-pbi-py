# Documentación por módulo

Esta documentación se generó a partir del código Python actual de `fix-rdl-pbi-py`.

## Navegación

Use el panel izquierdo del sitio para cambiar de módulo. También puede usar la tabla siguiente.

| Archivo | Rol | Descripción |
|---|---|---|
| [`auth.py`](auth.md) | Infraestructura / autenticación | Obtención del access token mediante Azure CLI para Fabric y Power BI. |
| [`config.py`](config.md) | Configuración | Carga y modelado de la configuración de post-deploy mediante `PostDeployConfig`. |
| [`diagnostics.py`](diagnostics.md) | Observabilidad y diagnóstico | Registro de ejecución, requests/responses HTTP, payloads decodificados y comandos cURL reproducibles. |
| [`fabric_connections.py`](fabric_connections.md) | Binding auxiliar de conexiones Fabric | Resolución auxiliar de conexiones Fabric Oracle y binding de Semantic Models mediante Fabric Connections. |
| [`gateway.py`](gateway.md) | Binding auxiliar de gateway Power BI | Implementación auxiliar y más detallada de descubrimiento, selección y verificación de gateway/datasource Power BI. |
| [`http_clients.py`](http_clients.md) | Infraestructura HTTP | Cliente HTTP común para Fabric y Power BI, manejo de errores y operaciones de larga duración (LRO). |
| [`main.py`](main.md) | Orquestación | Punto de entrada y orquestador del flujo target-only de post-deploy. |
| [`paginated.py`](paginated.md) | Remediación de definición RDL | Corrección in-place del XML RDL de los informes paginados, preservando su `itemId`. |
| [`powerbi_gateway.py`](powerbi_gateway.md) | Binding activo de gateway | Binding activo de Semantic Models con gateways compatibles mediante Power BI REST API. |
| [`powerbi_paginated.py`](powerbi_paginated.md) | Binding runtime de paginados | Binding runtime de informes paginados hacia los Semantic Models reales del workspace destino. |
| [`remediation.py`](remediation.md) | Remediación de RDL Visuals | Resolución de Paginated Reports y corrección de `itemId`/`workspaceId` en los RDL Visuals. |
| [`repository.py`](repository.md) | Descubrimiento local auxiliar | Descubrimiento auxiliar de elementos y RDL Visuals a partir de un repositorio local. |
| [`semantic_refresh.py`](semantic_refresh.md) | Refresh de Semantic Models | Ejecución y seguimiento del refresh de Semantic Models, equivalente a “Actualizar ahora”. |
| [`workspace.py`](workspace.md) | Acceso y descubrimiento de objetos Fabric | Descubrimiento de objetos Fabric y lectura/actualización de definiciones de Reports y Paginated Reports. |

## Cómo usar el panel lateral

El paquete incluye `mkdocs.yml` con el tema integrado **Read the Docs**, que genera un panel de navegación lateral.

Desde la carpeta raíz de este paquete:

```powershell
pip install mkdocs
mkdocs serve
```

Después abra la URL local mostrada por MkDocs, normalmente `http://127.0.0.1:8000/`.

También puede generar HTML estático con:

```powershell
mkdocs build
```

La salida queda en `site/`.