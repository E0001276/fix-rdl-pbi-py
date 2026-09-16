# `config.py`

**Rol:** Configuración

Carga y modelado de la configuración de post-deploy mediante `PostDeployConfig`.

## Responsabilidad dentro de la aplicación

Define el contrato de configuración consumido por el resto de módulos.

## Dependencias

- `json`
- `dataclasses:dataclass`
- `pathlib:Path`

## Clases

### `PostDeployConfig`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `load_config` | `load_config(path: str)` |

## Algoritmo / pseudocódigo

```text
INICIO
    abrir archivo JSON de configuración
    leer workspaceId y workspaceName
    leer flags de remediación, gateway y refresh
    construir PostDeployConfig
    devolver configuración
FIN
```

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | ruta del JSON de ambiente |
| Salida | instancia `PostDeployConfig` |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/config.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
