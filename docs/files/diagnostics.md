# `diagnostics.py`

Documentación del módulo Python [`src/diagnostics.py`](../../src/diagnostics.py).

## Responsabilidad del módulo

Genera trazabilidad detallada de ejecución y de llamadas HTTP sin persistir tokens Bearer.

## Dependencias

- `base64`
- `json`
- `re`
- `sys`
- `datetime: datetime, timezone`
- `pathlib: Path`

## Clases

### `_Tee`

#### `__init__(self, original, log_file)`

Inicializa la instancia y sus dependencias/estado interno.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `original` | `No especificado` | `Requerido` |
| `log_file` | `No especificado` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

#### `write(self, text)`

Escribe el texto tanto en el stream original como en el archivo de log.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `text` | `No especificado` | `Requerido` |

**Retorno**

Devuelve resultado de una llamada.

**Comportamiento y efectos**

Llamadas relevantes: `self.original.write`, `self.log_file.write`, `self.log_file.flush`.
Puede escribir archivos o crear directorios.

#### `flush(self)`

Fuerza el vaciado del stream original y del archivo de log.

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self.original.flush`, `self.log_file.flush`.

#### `isatty(self)`

Replica la capacidad TTY del stream original.

**Retorno**

Devuelve resultado de una llamada.

#### `encoding(self)`

Expone la codificación del stream original.

**Retorno**

Devuelve resultado de una llamada.

### `DiagnosticLogger`

Detailed, replay-oriented execution and HTTP diagnostics.

Authorization values are intentionally never persisted. Each HTTP request gets
a directory containing request/response metadata, a replayable curl command,
JSON bodies when present, and decoded InlineBase64 definition parts.

#### `__init__(self, log_root: Path)`

Inicializa la instancia y sus dependencias/estado interno.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `log_root` | `Path` | `Requerido` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self.http_dir.mkdir`, `self.execution_path.open`, `self._write_manifest`.
Puede escribir archivos o crear directorios.

#### `_write_manifest(self)`

Genera el `manifest.json` de la ejecución de diagnóstico.

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `json.dumps`.
Puede escribir archivos o crear directorios.

#### `close(self)`

Restaura stdout/stderr y cierra correctamente el archivo de log.

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self._execution_file.flush`, `self._execution_file.close`.

#### `_safe_name(value: str)`

Convierte un valor arbitrario en un nombre de archivo seguro.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `str` | `Requerido` |

**Retorno**

`str`

#### `_redact_headers(headers: dict)`

Redacta headers sensibles antes de persistirlos en diagnóstico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `headers` | `dict` | `Requerido` |

**Retorno**

`dict`

#### `_quote_ps(value: str)`

Escapa un valor para incluirlo de forma segura en un comando PowerShell.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `str` | `Requerido` |

**Retorno**

`str`

#### `_extract_inline_parts(self, data, destination: Path)`

Extrae y decodifica partes `InlineBase64` de requests/responses Fabric para inspección.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `data` | `No especificado` | `Requerido` |
| `destination` | `Path` | `Requerido` |

**Retorno**

No devuelve un valor útil (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `base64.b64decode`, `json.dumps`, `self._safe_name`.
Puede escribir archivos o crear directorios.

#### `log_http(self, method: str, url: str, request_headers: dict, request_json, response, token_label: str='ACCESS_TOKEN')`

Persiste metadata, request, response, curl reproducible y partes decodificadas de una llamada HTTP.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `method` | `str` | `Requerido` |
| `url` | `str` | `Requerido` |
| `request_headers` | `dict` | `Requerido` |
| `request_json` | `No especificado` | `Requerido` |
| `response` | `No especificado` | `Requerido` |
| `token_label` | `str` | `'ACCESS_TOKEN'` |

**Retorno**

No devuelve un valor explícito (`None`).

**Comportamiento y efectos**

Llamadas relevantes: `self._safe_name`, `self._redact_headers`, `print`, `json.dumps`, `self._extract_inline_parts`, `self._quote_ps`.
Escribe información de diagnóstico en consola.
Puede escribir archivos o crear directorios.

## Funciones

### `start_diagnostics(project_root: Path)`

Inicializa el sistema de diagnóstico y crea la carpeta de logs para la ejecución actual.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `project_root` | `Path` | `Requerido` |

**Retorno**

`DiagnosticLogger`

## Archivo fuente

Ruta: `src/diagnostics.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
