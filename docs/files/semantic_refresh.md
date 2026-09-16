# `semantic_refresh.py`

**Rol:** Refresh de Semantic Models

Ejecución y seguimiento del refresh de Semantic Models, equivalente a “Actualizar ahora”.

## Responsabilidad dentro de la aplicación

Solicita el refresh después del gateway binding y, si está configurado, espera hasta conocer el resultado final.

## Dependencias

- `time`

## Clases

Este módulo no define clases.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_dataset_info` | `_dataset_info(powerbi, workspace_id: str, dataset_id: str)` |
| `_latest_refresh` | `_latest_refresh(powerbi, workspace_id: str, dataset_id: str)` |
| `refresh_semantic_models` | `refresh_semantic_models(powerbi, workspace_items, config)` |

## Algoritmo / pseudocódigo

```text
PARA CADA Semantic Model
    consultar propiedades del dataset
    SI isRefreshable = false
        omitir
    FIN SI
    POST /refreshes
    SI waitForRefresh = true
        consultar último refresh periódicamente
        salir cuando status sea terminal
        fallar si corresponde según configuración
    FIN SI
FIN PARA
```

## APIs relacionadas

- `GET /groups/{workspaceId}/datasets/{datasetId}`
- `POST /groups/{workspaceId}/datasets/{datasetId}/refreshes`
- `GET /groups/{workspaceId}/datasets/{datasetId}/refreshes?$top=1`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | cliente Power BI + Semantic Models + flags de refresh |
| Salida | solicitud/estado del refresh |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/semantic_refresh.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
