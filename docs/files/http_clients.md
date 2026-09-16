# `http_clients.py`

Documentación del módulo Python [`src/http_clients.py`](../../src/http_clients.py).

## Responsabilidad del módulo

Implementa el cliente HTTP compartido y el manejo de operaciones Fabric de larga duración.

## Dependencias

- `time`
- `urllib.parse: urljoin`
- `requests`

## Clases

### `ApiClient`

#### `__init__(self, base_url: str, token: str, diagnostics=None, token_label: str='ACCESS_TOKEN')`

Inicializa la instancia y sus dependencias/estado interno.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `base_url` | `str` | `Requerido` |
| `token` | `str` | `Requerido` |
| `diagnostics` | `No especificado` | `None` |
| `token_label` | `str` | `'ACCESS_TOKEN'` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self.session.headers.update`.

#### `_url(self, path_or_url: str)`

Convierte una ruta relativa en una URL absoluta usando la URL base del cliente.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path_or_url` | `str` | `Requerido` |

**Retorno**

`str`

#### `_raise_for_status_with_body(response)`

Eleva un `HTTPError` enriquecido con el body de respuesta cuando la solicitud no fue exitosa.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `response` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor útil (`None`).

**Excepciones explícitas**

- `requests.HTTPError(f'{response.status_code} {response.reason} for {response.url}; response={body}', response=response)`

#### `_log(self, method: str, url: str, request_json, response)`

Envía request y response al registrador de diagnósticos, si está habilitado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `method` | `str` | `Requerido` |
| `url` | `str` | `Requerido` |
| `request_json` | `No especificado` | `Requerido` |
| `response` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self.diagnostics.log_http`.

#### `get(self, path_or_url: str, params=None)`

Ejecuta una solicitud HTTP GET autenticada y registra la respuesta.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path_or_url` | `str` | `Requerido` |
| `params` | `No especificado` | `None` |

**Retorno**

Devuelve valor `response`.

**Comportamiento y efectos**

Llamadas relevantes: `self._url`, `self.session.get`, `self._log`, `self._raise_for_status_with_body`.

#### `post(self, path_or_url: str, json=None, params=None)`

Ejecuta una solicitud HTTP POST autenticada y registra la respuesta.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path_or_url` | `str` | `Requerido` |
| `json` | `No especificado` | `None` |
| `params` | `No especificado` | `None` |

**Retorno**

Devuelve valor `response`.

**Comportamiento y efectos**

Llamadas relevantes: `self._url`, `self.session.post`, `self._log`, `self._raise_for_status_with_body`.

#### `patch(self, path_or_url: str, json=None, params=None)`

Ejecuta una solicitud HTTP PATCH autenticada y registra la respuesta.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path_or_url` | `str` | `Requerido` |
| `json` | `No especificado` | `None` |
| `params` | `No especificado` | `None` |

**Retorno**

Devuelve valor `response`.

**Comportamiento y efectos**

Llamadas relevantes: `self._url`, `self.session.patch`, `self._log`, `self._raise_for_status_with_body`.

#### `delete(self, path_or_url: str, params=None)`

Ejecuta una solicitud HTTP DELETE autenticada y registra la respuesta.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path_or_url` | `str` | `Requerido` |
| `params` | `No especificado` | `None` |

**Retorno**

Devuelve valor `response`.

**Comportamiento y efectos**

Llamadas relevantes: `self._url`, `self.session.delete`, `self._log`, `self._raise_for_status_with_body`.

#### `_fabric_operation_path(operation_id: str)`

Implementa la responsabilidad interna `_fabric_operation_path` del módulo `http_clients.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `operation_id` | `str` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Rutas/API construidas o utilizadas:
- `f'operations/{operation_id}'`
- `operations/`

#### `_fabric_result_path(operation_id: str)`

Implementa la responsabilidad interna `_fabric_result_path` del módulo `http_clients.py`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `operation_id` | `str` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Rutas/API construidas o utilizadas:
- `f'operations/{operation_id}/result'`
- `operations/`

#### `wait_for_lro_completion(self, response, timeout_seconds: int=300)`

Espera la finalización de una operación Fabric de larga duración (LRO).

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `response` | `No especificado` | `Requerido` |
| `timeout_seconds` | `int` | `300` |

**Retorno**

No devuelve un valor útil (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `time.sleep`, `self.get`, `self._fabric_operation_path`.
Realiza espera activa entre intentos de polling.

**Excepciones explícitas**

- `RuntimeError('Fabric returned HTTP 202 without x-ms-operation-id or Location.')`
- `TimeoutError(f'Fabric operation did not finish within {timeout_seconds} seconds.')`
- `RuntimeError(f"Fabric operation {operation_id or ''} finished with status {status}: {state}")`

#### `get_json_lro_result(self, response, timeout_seconds: int=300)`

Return JSON for an immediate response or poll a Fabric LRO to completion.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `response` | `No especificado` | `Requerido` |
| `timeout_seconds` | `int` | `300` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `time.sleep`, `self.get`, `self._fabric_operation_path`, `self.get(result_url).json`, `self.get(self._fabric_result_path(operation_id)).json`, `self._fabric_result_path`.
Realiza espera activa entre intentos de polling.

**Excepciones explícitas**

- `RuntimeError('Fabric returned HTTP 202 without x-ms-operation-id or Location.')`
- `TimeoutError(f'Fabric operation did not finish within {timeout_seconds} seconds.')`
- `RuntimeError(f"Fabric operation {operation_id or ''} finished with status {status}: {state}")`
- `RuntimeError('Fabric LRO succeeded but no operation id or result Location was available.')`

## Archivo fuente

Ruta: `src/http_clients.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
