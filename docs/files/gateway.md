# `gateway.py`

Documentación del módulo Python [`src/gateway.py`](../../src/gateway.py).

## Responsabilidad del módulo

Contiene una implementación auxiliar de binding explícito a gateway/datasource y validación por polling.

## Dependencias

- `json`
- `time`
- `dataclasses: dataclass`
- `requests`

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
| `datasource_id` | `str` | `''` |
| `datasource_name` | `str` | `''` |
| `message` | `str` | `''` |

## Funciones

### `_normalize(value)`

Implementa la responsabilidad interna `_normalize` del módulo `gateway.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

`str`

### `_connection_details(value)`

Obtiene de forma segura el diccionario `connectionDetails` de un datasource.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `No especificado` | `Requerido` |

**Retorno**

Devuelve diccionario, valor `value`, valor calculado.

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`.

### `_oracle_matches_expected(datasource, expected_database: str)`

Implementa la responsabilidad interna `_oracle_matches_expected` del módulo `gateway.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `datasource` | `No especificado` | `Requerido` |
| `expected_database` | `str` | `Requerido` |

**Retorno**

`bool`

### `_describe_details(datasource)`

Implementa la responsabilidad interna `_describe_details` del módulo `gateway.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `datasource` | `No especificado` | `Requerido` |

**Retorno**

`str`

### `_get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str)`

Obtiene los datasources registrados para un modelo semántico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

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

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}/Default.DiscoverGateways'`
- `groups/`
- `/Default.DiscoverGateways`

### `_get_gateway_datasources(powerbi, gateway_id: str)`

Implementa la responsabilidad interna `_get_gateway_datasources` del módulo `gateway.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `gateway_id` | `str` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.

### `_bind_to_gateway(powerbi, workspace_id: str, dataset_id: str, gateway_id: str, datasource_id: str)`

Envía la solicitud de vinculación del modelo semántico con un gateway y datasource específicos.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |
| `gateway_id` | `str` | `Requerido` |
| `datasource_id` | `str` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.post`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}/Default.BindToGateway'`
- `groups/`
- `/Default.BindToGateway`

### `_verify_gateway_binding(powerbi, workspace_id: str, dataset_id: str, expected_gateway_id: str, expected_datasource_id: str, expected_database: str, max_attempts: int=10, delay_seconds: int=3)`

Poll dataset datasources until the expected gateway binding is visible.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |
| `expected_gateway_id` | `str` | `Requerido` |
| `expected_datasource_id` | `str` | `Requerido` |
| `expected_database` | `str` | `Requerido` |
| `max_attempts` | `int` | `10` |
| `delay_seconds` | `int` | `3` |

**Retorno**

Devuelve tupla.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `time.sleep`.
Escribe información de diagnóstico en consola.
Realiza espera activa entre intentos de polling.

### `_find_matching_gateway_datasources(powerbi, gateways, expected_database: str)`

Localiza datasources de gateway Oracle que coinciden con la base esperada.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `gateways` | `No especificado` | `Requerido` |
| `expected_database` | `str` | `Requerido` |

**Retorno**

Devuelve tupla.

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

### `bind_semantic_models_to_gateway(powerbi, workspace_items, config)`

Orquesta la vinculación de los modelos semánticos del workspace con el gateway Oracle esperado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError('expectedOracleDatabase is required for safe automatic gateway binding.')`
- `RuntimeError(f'Unable to safely bind {len(failures)} semantic model gateway relationship(s).')`

## Archivo fuente

Ruta: `src/gateway.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
