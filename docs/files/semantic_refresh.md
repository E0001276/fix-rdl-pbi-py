# `semantic_refresh.py`

Documentación del módulo Python [`src/semantic_refresh.py`](../../src/semantic_refresh.py).

## Responsabilidad del módulo

Ejecuta y monitoriza el refresh de Semantic Models.

## Dependencias

- `time`

## Funciones

### `_dataset_info(powerbi, workspace_id: str, dataset_id: str)`

Obtiene las propiedades de un modelo semántico mediante Power BI REST API.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |

**Retorno**

`dict`

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get(f'groups/{workspace_id}/datasets/{dataset_id}').json`, `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}'`
- `groups/`

### `_latest_refresh(powerbi, workspace_id: str, dataset_id: str)`

Obtiene el refresh más reciente de un modelo semántico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_id` | `str` | `Requerido` |
| `dataset_id` | `str` | `Requerido` |

**Retorno**

`dict | None`

**Comportamiento y efectos**

Llamadas relevantes: `powerbi.get`.
Rutas/API construidas o utilizadas:
- `f'groups/{workspace_id}/datasets/{dataset_id}/refreshes'`
- `groups/`
- `/refreshes`

### `refresh_semantic_models(powerbi, workspace_items, config)`

Solicita refresh de los modelos semánticos y, si se configura, espera su estado terminal.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `powerbi` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve lista, valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`, `powerbi.post`, `time.sleep`.
Rutas/API construidas o utilizadas:
- `f'groups/{config.workspace_id}/datasets/{model.id}/refreshes'`
- `groups/`
- `/refreshes`
Escribe información de diagnóstico en consola.
Realiza espera activa entre intentos de polling.

**Excepciones explícitas**

- `RuntimeError(f'Unable to refresh {len(failures)} semantic model(s).')`
- `RuntimeError('Power BI reports isRefreshable=false for this semantic model.')`
- `TimeoutError(f'Refresh did not complete within {config.refresh_timeout_seconds} seconds.')`
- `RuntimeError(f'Refresh finished with status {status}. {error}')`

## Archivo fuente

Ruta: `src/semantic_refresh.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
