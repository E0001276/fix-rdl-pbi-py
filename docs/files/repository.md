# `repository.py`

Documentación del módulo Python [`src/repository.py`](../../src/repository.py).

## Responsabilidad del módulo

Descubre objetos y RDL Visuals desde una copia local del repositorio; es una utilidad auxiliar.

## Dependencias

- `json`
- `dataclasses: dataclass`
- `pathlib: Path`

## Clases

### `RepoItem`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `kind` | `str` | `Requerido` |
| `display_name` | `str` | `Requerido` |
| `path` | `Path` | `Requerido` |

### `RdlVisual`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `report_name` | `str` | `Requerido` |
| `page_name` | `str` | `Requerido` |
| `report_path` | `Path` | `Requerido` |
| `visual_path` | `Path` | `Requerido` |
| `old_item_id` | `str` | `Requerido` |
| `old_workspace_id` | `str` | `Requerido` |

## Funciones

### `_platform_display_name(path: Path)`

Lee `.platform` y obtiene el `displayName` del item del repositorio.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `path` | `Path` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `json.loads`.

### `discover_repository(repository_root: str)`

Descubre Reports, Semantic Models, Paginated Reports y RDL Visuals directamente desde el repositorio local.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `repository_root` | `str` | `Requerido` |

**Retorno**

Devuelve tupla.

**Comportamiento y efectos**

Llamadas relevantes: `Path`, `json.loads`.

**Excepciones explícitas**

- `FileNotFoundError(f'Repository root not found: {root}')`

## Archivo fuente

Ruta: `src/repository.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
