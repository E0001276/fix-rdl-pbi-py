# `http_clients.py`

**Rol:** Infraestructura HTTP

Cliente HTTP común para Fabric y Power BI, manejo de errores y operaciones de larga duración (LRO).

## Responsabilidad dentro de la aplicación

Uniforma autenticación Bearer, construcción de URLs, logging HTTP, propagación de errores y polling de operaciones Fabric.

## Dependencias

- `time`
- `urllib.parse:urljoin`
- `requests`

## Clases

### `ApiClient`

| Método | Firma |
|---|---|
| `__init__` | `__init__(self, base_url: str, token: str, diagnostics=None, token_label: str='ACCESS_TOKEN')` |
| `_url` | `_url(self, path_or_url: str)` |
| `_raise_for_status_with_body` | `_raise_for_status_with_body(response)` |
| `_log` | `_log(self, method: str, url: str, request_json, response)` |
| `get` | `get(self, path_or_url: str, params=None)` |
| `post` | `post(self, path_or_url: str, json=None, params=None)` |
| `patch` | `patch(self, path_or_url: str, json=None, params=None)` |
| `delete` | `delete(self, path_or_url: str, params=None)` |
| `_fabric_operation_path` | `_fabric_operation_path(operation_id: str)` |
| `_fabric_result_path` | `_fabric_result_path(operation_id: str)` |
| `wait_for_lro_completion` | `wait_for_lro_completion(self, response, timeout_seconds: int=300)` |
| `get_json_lro_result` | `get_json_lro_result(self, response, timeout_seconds: int=300)` |

## Funciones de módulo

No define funciones de módulo.

## Algoritmo / pseudocódigo

```text
INICIO
    construir URL absoluta
    agregar Authorization Bearer
    ejecutar GET/POST/PATCH/DELETE
    registrar diagnóstico
    SI status no exitoso
        incluir body en HTTPError
    FIN SI
    SI operación Fabric devuelve 202
        obtener x-ms-operation-id
        consultar /operations/{id} hasta estado terminal
        obtener /result cuando corresponda
    FIN SI
FIN
```

## APIs relacionadas

- `GET /v1/operations/{operationId}`
- `GET /v1/operations/{operationId}/result`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | base URL, token y request |
| Salida | `requests.Response` o resultado LRO |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/http_clients.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
