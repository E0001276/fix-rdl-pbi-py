# `powerbi_gateway.py`

**Rol:** Binding activo de gateway

Binding activo de Semantic Models con gateways compatibles mediante Power BI REST API.

## Responsabilidad dentro de la aplicación

Realiza el binding de los Semantic Models al gateway compatible antes del refresh y antes de la remediación de paginados.

## Dependencias

- `json`
- `dataclasses:dataclass`

## Clases

### `GatewayBindingResult`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_norm` | `_norm(value)` |
| `_details` | `_details(value)` |
| `_matches_expected_oracle` | `_matches_expected_oracle(datasource: dict, expected_database: str)` |
| `_get_dataset_datasources` | `_get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str)` |
| `_discover_gateways` | `_discover_gateways(powerbi, workspace_id: str, dataset_id: str)` |
| `bind_semantic_models_to_gateway` | `bind_semantic_models_to_gateway(powerbi, workspace_items, config)` |

## Algoritmo / pseudocódigo

```text
PARA CADA Semantic Model
    obtener datasources actuales
    identificar Oracle esperado
    SI ya existe binding válido
        continuar
    FIN SI
    DiscoverGateways
    seleccionar gateway/datasource compatible
    POST Default.BindToGateway
FIN PARA
```

## APIs relacionadas

- `GET /groups/{workspaceId}/datasets/{datasetId}/datasources`
- `GET /groups/{workspaceId}/datasets/{datasetId}/Default.DiscoverGateways`
- `POST /groups/{workspaceId}/datasets/{datasetId}/Default.BindToGateway`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | cliente Power BI + Semantic Models + config |
| Salida | binding del dataset al gateway compatible |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/powerbi_gateway.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
