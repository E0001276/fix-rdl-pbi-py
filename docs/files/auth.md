# `auth.py`

Documentación del módulo Python [`src/auth.py`](../../src/auth.py).

## Responsabilidad del módulo

Gestiona la autenticación mediante Azure CLI y entrega access tokens para Fabric REST API y Power BI REST API.

## Dependencias

- `json`
- `os`
- `shutil`
- `subprocess`
- `pathlib: Path`

## Funciones

### `_find_azure_cli()`

Return an Azure CLI command that works on Windows and Linux.

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `shutil.which`, `Path`.

**Excepciones explícitas**

- `FileNotFoundError("Azure CLI was not found. Install Azure CLI and make sure 'az' is available in PATH.")`

### `get_access_token(resource: str)`

Obtiene un access token mediante Azure CLI para el recurso solicitado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `resource` | `str` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `subprocess.run`, `json.loads`.

## Archivo fuente

Ruta: `src/auth.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
