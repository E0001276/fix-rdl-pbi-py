# `fabric_connections.py`

Documentación del módulo Python [`src/fabric_connections.py`](../../src/fabric_connections.py).

## Responsabilidad del módulo

Contiene el flujo auxiliar para descubrir y seleccionar conexiones Fabric Oracle y vincular modelos semánticos mediante conexiones Fabric.

## Dependencias

- `dataclasses: dataclass`

## Clases

### `ConnectionMatch`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `id` | `str` | `Requerido` |
| `display_name` | `str` | `Requerido` |
| `gateway_id` | `str` | `Requerido` |
| `connectivity_type` | `str` | `Requerido` |
| `connection_type` | `str` | `Requerido` |
| `path` | `str` | `Requerido` |
| `raw` | `dict` | `Requerido` |

## Funciones

### `_list_all_connections(fabric)`

Enumera todas las conexiones Fabric visibles para el usuario, siguiendo la paginación.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |

**Retorno**

Devuelve valor `items`.

**Comportamiento y efectos**

Llamadas relevantes: `fabric.get`.
Rutas/API construidas o utilizadas:
- `connections`

### `_normalize(value)`

Implementa la responsabilidad interna `_normalize` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

`str`

### `_safe_display_name(connection: dict)`

Implementa la responsabilidad interna `_safe_display_name` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |

**Retorno**

`str`

### `_is_oracle(connection: dict)`

Implementa la responsabilidad interna `_is_oracle` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |

**Retorno**

`bool`

### `_is_on_premises_gateway(connection: dict)`

Implementa la responsabilidad interna `_is_on_premises_gateway` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |

**Retorno**

`bool`

### `_matches_expected_exact(connection: dict, expected: str)`

Require the shared Oracle connection to match by BOTH name and path.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |
| `expected` | `str` | `Requerido` |

**Retorno**

`bool`

### `_as_match(connection: dict)`

Implementa la responsabilidad interna `_as_match` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |

**Retorno**

`ConnectionMatch`

### `_format_candidate(connection: dict)`

Implementa la responsabilidad interna `_format_candidate` del módulo `fabric_connections.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `connection` | `dict` | `Requerido` |

**Retorno**

`str`

### `_resolve_connection(fabric, expected_oracle_database: str)`

Resuelve la conexión Oracle on-premises que coincide exactamente con la base esperada.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |
| `expected_oracle_database` | `str` | `Requerido` |

**Retorno**

`ConnectionMatch`

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError(f"Unable to safely resolve exactly one OnPremisesGateway Oracle connection for '{expected_oracle_database}'. Candidates: {candidates}.")`

### `bind_semantic_models_to_connections(fabric, workspace_items, config)`

Vincula modelos semánticos con una conexión Fabric cuando este flujo auxiliar está habilitado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve lista, valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `fabric.post`.
Rutas/API construidas o utilizadas:
- `f'workspaces/{config.workspace_id}/semanticModels/{model.id}/bindConnection'`
- `workspaces/`
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError('expectedOracleDatabase is required for Fabric connection binding.')`
- `RuntimeError('The resolved Fabric connection is missing required metadata.')`
- `RuntimeError('The resolved Fabric connection is not an OnPremisesGateway connection.')`
- `RuntimeError(f'Unable to bind {len(failures)} semantic model connection(s) with Fabric REST.')`

## Archivo fuente

Ruta: `src/fabric_connections.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
