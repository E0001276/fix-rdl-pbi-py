# `gateway.py`

**Rol:** Binding auxiliar de gateway Power BI

Implementación auxiliar y más detallada de descubrimiento, selección y verificación de gateway/datasource Power BI.

> **Nota:** este módulo contiene una implementación auxiliar/alternativa. El flujo activo de `main.py` importa `bind_semantic_models_to_gateway` desde `powerbi_gateway.py`.

## Responsabilidad dentro de la aplicación

Contiene una estrategia auxiliar con mayor verificación explícita de gateway y datasource.

## Dependencias

- `json`
- `time`
- `dataclasses:dataclass`
- `requests`

## Clases

### `GatewayBindingResult`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_normalize` | `_normalize(value)` |
| `_connection_details` | `_connection_details(value)` |
| `_oracle_matches_expected` | `_oracle_matches_expected(datasource, expected_database: str)` |
| `_describe_details` | `_describe_details(datasource)` |
| `_get_dataset_datasources` | `_get_dataset_datasources(powerbi, workspace_id: str, dataset_id: str)` |
| `_discover_gateways` | `_discover_gateways(powerbi, workspace_id: str, dataset_id: str)` |
| `_get_gateway_datasources` | `_get_gateway_datasources(powerbi, gateway_id: str)` |
| `_bind_to_gateway` | `_bind_to_gateway(powerbi, workspace_id: str, dataset_id: str, gateway_id: str, datasource_id: str)` |
| `_verify_gateway_binding` | `_verify_gateway_binding(powerbi, workspace_id: str, dataset_id: str, expected_gateway_id: str, expected_datasource_id: str, expected_database: str, max_attempts: int=10, delay_seconds: int=3)` |
| `_find_matching_gateway_datasources` | `_find_matching_gateway_datasources(powerbi, gateways, expected_database: str)` |
| `bind_semantic_models_to_gateway` | `bind_semantic_models_to_gateway(powerbi, workspace_items, config)` |

## Algoritmo / pseudocódigo

```text
INICIO
    PARA CADA Semantic Model
        obtener datasources del dataset
        validar si ya apunta al Oracle esperado
        descubrir gateways compatibles
        listar datasources del gateway
        seleccionar datasource Oracle esperado
        BindToGateway
        verificar binding mediante reintentos
    FIN PARA
FIN
```

## APIs relacionadas

- `GET /groups/{workspaceId}/datasets/{datasetId}/datasources`
- `GET /groups/{workspaceId}/datasets/{datasetId}/Default.DiscoverGateways`
- `GET /gateways/{gatewayId}/datasources`
- `POST /groups/{workspaceId}/datasets/{datasetId}/Default.BindToGateway`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | cliente Power BI, workspace_items y config |
| Salida | resultado de binding y verificación |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** ningún otro módulo Python detectado de forma directa.

## Código fuente analizado

Archivo: `src/gateway.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
