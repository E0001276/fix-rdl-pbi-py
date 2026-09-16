# `powerbi_gateway.py`

Documentación del módulo Python [`src/powerbi_gateway.py`](../../src/powerbi_gateway.py).

## Responsabilidad del módulo

Implementa el binding activo de Semantic Models al gateway compatible mediante Power BI REST API.

## Dependencias

- `json`
- `dataclasses: dataclass`

## Clases

### `GatewayBindingResult`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `semantic_model_id` | `str` | `Requerido` |
| `semantic_model_name` | `str` | `Requerido` |
| `status` | `str` | `Requerido` |
| `gateway_id` | `str` | `''` |
| `gateway_name` | `str` | `''` |
| `message` | `str` | `''` |

## Funciones

### `_norm(value)`

Normaliza un valor textual para comparaciones tolerantes a mayúsculas/minúsculas y espacios.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

`str`

### `_details(value)`

Convierte `connectionDetails` a un diccionario utilizable.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

`dict`

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`.

### `_matches_expected_oracle(datasource: dict, expected_database: str)`

Comprueba que un datasource sea Oracle y corresponda a la base esperada.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `datasource` | `dict` | `Requerido` |
| `expected_database` | `str` | `Requerido` |

**Retorno**

`bool`

### `_get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str)`

Obtiene los datasources registrados para un modelo semántico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |

**Retorno**

`list[dict]`

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}/datasources'`
- `groups/`

### `_discover_gateways(powerbi, workspace_id: str, dataset_id: str)`

Obtiene los gateways compatibles que Power BI expone para un modelo semántico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |

**Retorno**

`list[dict]`

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}/Default.DiscoverGateways'`
- `groups/`
- `/Default.DiscoverGateways`

### `bind_semantic_models_to_gateway(powerbi, workspace_items, config)`

Mirror the proven .NET BindToGateway flow using target workspace only.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve lista, valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `powerbi.post`.
Rutas/API construidas o utilizadas:
- `Mirror the proven .NET BindToGateway flow using target workspace only.

    Resolution is target-only: inspect each target semantic model's Oracle datasource,
    ask Power BI which gateways can bind that model, require exactly one compatible
    gateway, and call Default.BindToGateway. No source workspace is consulted.
    `
- `  Calling Default.BindToGateway...`
- `f'Default.DiscoverGateways failed: {exc}'`
- `f'groups/{config.workspace_id}/datasets/{model.id}/Default.BindToGateway'`
- `f'Default.BindToGateway failed: {exc}'`
- `Default.DiscoverGateways failed: `
- `groups/`
- `/Default.BindToGateway`
- `Default.BindToGateway failed: `
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError(f'Unable to safely bind {len(failures)} semantic model gateway relationship(s).')`

## Archivo fuente

Ruta: `src/powerbi_gateway.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
