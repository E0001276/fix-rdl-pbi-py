# `fabric_connections.py`

**Rol:** Binding auxiliar de conexiones Fabric

Resolución auxiliar de conexiones Fabric Oracle y binding de Semantic Models mediante Fabric Connections.

> **Nota:** este módulo existe como implementación auxiliar. El flujo activo de `main.py` usa `powerbi_gateway.py` para el binding principal.

## Responsabilidad dentro de la aplicación

Implementa una estrategia de binding usando conexiones Fabric, separada del flujo activo de gateway Power BI.

## Dependencias

- `dataclasses:dataclass`

## Clases

### `ConnectionMatch`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_list_all_connections` | `_list_all_connections(fabric)` |
| `_normalize` | `_normalize(value)` |
| `_safe_display_name` | `_safe_display_name(connection: dict)` |
| `_is_oracle` | `_is_oracle(connection: dict)` |
| `_is_on_premises_gateway` | `_is_on_premises_gateway(connection: dict)` |
| `_matches_expected_exact` | `_matches_expected_exact(connection: dict, expected: str)` |
| `_as_match` | `_as_match(connection: dict)` |
| `_format_candidate` | `_format_candidate(connection: dict)` |
| `_resolve_connection` | `_resolve_connection(fabric, expected_oracle_database: str)` |
| `bind_semantic_models_to_connections` | `bind_semantic_models_to_connections(fabric, workspace_items, config)` |

## Algoritmo / pseudocódigo

```text
INICIO
    listar conexiones Fabric disponibles
    filtrar conexiones Oracle
    priorizar OnPremisesGateway
    buscar coincidencia exacta con expectedOracleDatabase
    PARA CADA Semantic Model
        bindConnection hacia la conexión seleccionada
    FIN PARA
FIN
```

## APIs relacionadas

- `GET /v1/connections`
- `POST /v1/workspaces/{workspaceId}/semanticModels/{semanticModelId}/bindConnection`

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | cliente Fabric, workspace_items y config |
| Salida | binding de Semantic Models o error de resolución |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** ningún otro módulo Python detectado de forma directa.

## Código fuente analizado

Archivo: `src/fabric_connections.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
