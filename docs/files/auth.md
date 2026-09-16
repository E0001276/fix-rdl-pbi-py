# `auth.py`

**Rol:** Infraestructura / autenticación

Obtención del access token mediante Azure CLI para Fabric y Power BI.

## Responsabilidad dentro de la aplicación

Aísla la dependencia de Azure CLI y devuelve únicamente el token requerido por los clientes HTTP.

## Dependencias

- `json`
- `os`
- `shutil`
- `subprocess`
- `pathlib:Path`

## Clases

Este módulo no define clases.

## Funciones de módulo

| Función | Firma |
|---|---|
| `_find_azure_cli` | `_find_azure_cli()` |
| `get_access_token` | `get_access_token(resource: str)` |

## Algoritmo / pseudocódigo

```text
INICIO
    localizar ejecutable de Azure CLI
    ejecutar: az account get-access-token --resource <resource>
    validar código de salida
    parsear JSON
    devolver accessToken
FIN
```

## Entradas y salidas principales

| Tipo | Valor |
|---|---|
| Entrada | resource URL de Azure AD |
| Salida | access token como `str` |

## Relación con otros módulos

**Importa módulos internos:** ninguno.

**Es utilizado por:** [`main.py`](main.md)

## Código fuente analizado

Archivo: `src/auth.py`

> Esta página documenta el comportamiento observado en el archivo fuente actual. No describe comportamiento que no esté representado por este código.
