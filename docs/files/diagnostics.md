# `diagnostics.py`

**Rol:** Observabilidad y diagnóstico

Registro de ejecución, requests/responses HTTP, payloads decodificados y comandos cURL reproducibles.

## Responsabilidad dentro de la aplicación

Genera evidencia auditable de cada ejecución sin persistir el token Bearer real.

## Dependencias

- `base64`
- `json`
- `re`
- `sys`
- `datetime:datetime, timezone`
- `pathlib:Path`

## Clases

### `_Tee`

| Método | Firma |
|---|---|
| `__init__` | `__init__(self, original, log_file)` |
| `write` | `write(self, text)` |
| `flush` | `flush(self)` |
| `isatty` | `isatty(self)` |
| `encoding` | `encoding(self)` |

### `DiagnosticLogger`

| Método | Firma |
|---|---|
| `__init__` | `__init__(self, log_root: Path)` |
| `_write_manifest` | `_write_manifest(self)` |
| `close` | `close(self)` |
| `_safe_name` | `_safe_name(value: str)` |
| `_redact_headers` | `_redact_headers(headers: dict)` |
| `_quote_ps` | `_quote_ps(value: str)` |
| `_extract_inline_parts` | `_extract_inline_parts(self, data, destination: Path)` |
| `log_http` | `log_http(self, method: str, url: str, request_headers: dict, request_json, response, token_label: str='ACCESS_TOKEN')` |

## Funciones de módulo

| Función | Firma |
|---|---|
| `start_diagnostics` | `start_diagnostics(project_root: Path)` |

## Algoritmo / pseudocódigo

```text
INICIO
    crear carpeta log/postdeploy_YYYYMMDD_HHMMSS
    redirigir stdout/stderr a execution.log y consola
    PARA CADA request HTTP
        redactar Authorization
        guardar metadata, request, response y curl
        decodificar partes InlineBase64 cuando existan
    FIN PARA
    escribir manifest.json
FIN
```

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | requests/responses HTTP y salida de consola |
| Salida | carpeta `log/postdeploy_*` con evidencia |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/diagnostics.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
