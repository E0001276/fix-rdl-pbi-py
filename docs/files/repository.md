# `repository.py`

**Rol:** Descubrimiento local auxiliar

Descubrimiento auxiliar de elementos y RDL Visuals a partir de un repositorio local.

> **Nota:** este módulo trabaja sobre archivos locales del repositorio. El flujo target-only activo de `main.py` descubre objetos directamente en Fabric mediante `workspace.py`.

## Responsabilidad dentro de la aplicación

Permite inventariar definiciones desde disco y modelarlas en estructuras simples.

## Dependencias

- `json`
- `dataclasses:dataclass`
- `pathlib:Path`

## Clases

### `RepoItem`

Clase de datos sin métodos explícitos.

### `RdlVisual`

Clase de datos sin métodos explícitos.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_platform_display_name` | `_platform_display_name(path: Path)` |
| `discover_repository` | `discover_repository(repository_root: str)` |

## Algoritmo / pseudocódigo

```text
INICIO
    recorrer repositorio local
    descubrir .platform y nombres de elementos
    abrir visual.json
    detectar visualType = rdlVisual
    construir objetos RepoItem y RdlVisual
    devolver inventario local
FIN
```

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | ruta de repositorio local |
| Salida | inventario de `RepoItem`/`RdlVisual` |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** ningún otro módulo Python detectado de forma directa.

## Código fuente analizado

Archivo: `src/repository.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
