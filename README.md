# fix-rdl-pbi-py
fix-rdl-pbi-py

## Ejecución automatizada Git -> Fabric -> FIX -> Git

El FIX original se conserva en `src/main.py`.

Para el flujo completo desde GitHub Actions utilice `src/deploy.py`:

```bash
python src/deploy.py \
  --config src/config/ws-chloar.yaml \
  --expected-branch "$TARGET_BRANCH" \
  --expected-owner "$GITHUB_REPOSITORY_OWNER" \
  --expected-repository "$GITHUB_REPOSITORY_NAME"
```

Si el Service Principal requiere una conexión de GitHub configurada en Fabric,
pase el identificador de la conexión mediante la variable de entorno:

```bash
export FABRIC_GIT_CONNECTION_ID="<connection-id>"
```

También puede pasarse con `--git-connection-id`.

`deploy.py` realiza, en este orden:

1. valida que el workspace esté conectado e inicializado con Git;
2. valida opcionalmente proveedor, propietario, repositorio y rama conectados;
3. sincroniza Git -> Workspace mediante `updateFromGit` y espera el LRO;
4. ejecuta sin cambios el FIX existente (`run_post_deploy`);
5. comprueba que la rama remota no cambió durante el FIX;
6. si el FIX produjo cambios, ejecuta `commitToGit` y espera el LRO;
7. si no hubo cambios, no genera commit.

Configuración opcional por ambiente:

```yaml
gitAutomation:
  enabled: true
  lroTimeoutSeconds: 1800
  commitMessage: "chore(fabric): apply Power BI post-deploy fixes [skip ci]"
  allowOverrideItems: true
  requireCleanWorkspaceBeforeUpdate: true
```

El `connectionId` no es obligatorio en el YAML si se proporciona mediante
`FABRIC_GIT_CONNECTION_ID` o `--git-connection-id`.

El mensaje predeterminado de `commitToGit` incluye `[skip ci]` para evitar que el
commit automático del FIX vuelva a disparar workflows basados en `push`.
