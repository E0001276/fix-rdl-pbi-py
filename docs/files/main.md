# `main.py`

Documentación del módulo Python [`src/main.py`](../../src/main.py).

## Responsabilidad del módulo

Orquesta la ejecución completa del post-deploy: configuración, autenticación, descubrimiento, gateway binding, refresh, remediación de paginados y corrección de RDL Visuals.

## Dependencias

- `argparse`
- `pathlib: Path`
- `truststore`
- `auth: get_access_token`
- `config: load_config`
- `diagnostics: start_diagnostics`
- `powerbi_gateway: bind_semantic_models_to_gateway`
- `semantic_refresh: refresh_semantic_models`
- `http_clients: ApiClient`
- `paginated: remediate_paginated_reports`
- `powerbi_paginated: bind_paginated_reports_to_semantic_models`
- `remediation: apply_remediation, summarize_discovery`
- `workspace: discover_paginated_report_definitions, discover_report_definitions, list_fabric_workspace_items`

## Funciones

### `build_parser()`

Construye el parser de argumentos de línea de comandos de la aplicación.

**Retorno**

`argparse.ArgumentParser`

**Comportamiento y efectos**

Llamadas relevantes: `Path`.

### `_section(title: str)`

Imprime un encabezado visual para separar etapas de la ejecución en consola.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `title` | `str` | `Requerido` |

**Retorno**

`None`

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `main()`

Punto de entrada de la aplicación; prepara argumentos, diagnósticos y manejo global de errores.

**Retorno**

`None`

**Comportamiento y efectos**

Llamadas relevantes: `print`, `Path`.
Escribe información de diagnóstico en consola.

### `_main(args, diagnostics)`

Orquesta el flujo completo de post-deploy sobre el workspace destino.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `args` | `No especificado` | `Requerido` |
| `diagnostics` | `No especificado` | `Requerido` |

**Retorno**

`None`

**Comportamiento y efectos**

Llamadas relevantes: `print`, `Path`.
Escribe información de diagnóstico en consola.

## Archivo fuente

Ruta: `src/main.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
