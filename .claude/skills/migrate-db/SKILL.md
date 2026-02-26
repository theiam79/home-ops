---
name: migrate-db
description: Migrate an app's PostgreSQL database from an external source (e.g., Unraid) to a CNPG cluster with S3 backups to Garage
argument-hint: <app-name> <namespace> <source-host> <source-db> <source-user>
---

# Migrate a PostgreSQL Database to CNPG

This skill guides the process of migrating an external PostgreSQL database into a CloudNative-PG (CNPG) cluster with barman-cloud S3 backups to Garage.

## Prerequisites

The user must provide:
- **App name** (used as `${APP}` throughout)
- **Namespace** where the app lives
- **Source PG host** (IP of external PG, e.g., `192.168.20.x`)
- **Source database name** and **user**
- **Bitwarden UUID** for the source PG password

The following must already exist in the cluster:
- `cloudnative-pg` and `cloudnative-pg-barman-cloud` in the `database` namespace
- `external-secrets` with `ClusterSecretStore` named `bitwarden-secretsmanager`
- S3 bucket `cnpg` on Garage (`garage.internal:3900`) with appropriate access key
- A temporary firewall rule allowing cluster VLAN to reach the source PG host on TCP 5432

## Directory Structure

Create a `db/` directory alongside the app's existing `app/` directory:

```
kubernetes/apps/<namespace>/<app>/
├── ks.yaml              # Split into two Flux Kustomizations
├── app/
│   └── ...              # Existing app resources
└── db/
    ├── kustomization.yaml
    ├── cluster.yaml       # CNPG Cluster + ObjectStore + ScheduledBackup
    └── cnpg-externalsecret.yaml  # S3 creds + source PG password
```

## Step 1: Split ks.yaml into db + app Kustomizations

The app's `ks.yaml` must have TWO Flux Kustomizations:

1. **`<app>-pg`** (database) — `wait: true`, depends on `cloudnative-pg`, `cloudnative-pg-barman-cloud`, `external-secrets`
2. **`<app>`** (application) — depends on `<app>-pg`

This ensures the CNPG cluster (and its auto-generated `<app>-pg-app` secret) exists before the app pod starts.

Reference: `kubernetes/apps/auth/lldap/ks.yaml`

## Step 2: Create db/cnpg-externalsecret.yaml

Contains S3 credentials for Garage backups plus the source PG password (temporary, for import).

- Garage S3 credentials use shared Bitwarden UUIDs:
  - Access Key: `98ff717f-76c7-4bba-8f96-b3fa0075db66`
  - Secret Key: `7917e6a9-f031-4ce6-95c9-b3fa0075f3c7`
- The source PG password UUID is provided by the user
- Target secret name: `<app>-cnpg-secret`

Reference: `kubernetes/apps/auth/lldap/db/cnpg-externalsecret.yaml`

## Step 3: Create db/cluster.yaml

A single file containing three resources:

### CNPG Cluster (initial deploy with import)
- `imageName: ghcr.io/cloudnative-pg/postgresql:17` (do NOT use `imageCatalogRef` — the `ClusterImageCatalog` may not exist)
- `cnpg.io/skipEmptyWalArchiveCheck: "enabled"` annotation
- Bootstrap uses `initdb.import` with `type: microservice` pointing to the source
- Configure barman-cloud plugin as WAL archiver with `serverName: <app>-pg-v1`
- Two `externalClusters`: one for the source PG (import), one for barman-cloud (recovery)
- Storage class: `ceph-block`

### ObjectStore
- `destinationPath: s3://cnpg/<app>/`
- `endpointURL: http://garage.internal:3900`
- S3 credentials from `<app>-cnpg-secret`
- Include `AWS_REQUEST_CHECKSUM_CALCULATION` and `AWS_RESPONSE_CHECKSUM_VALIDATION` env vars set to `when_required`

### ScheduledBackup
- Schedule: `0 0 2 * * *` (daily at 2 AM)
- `immediate: true` to trigger first backup right away
- Method: `plugin` with `barman-cloud.cloudnative-pg.io`

Reference: `kubernetes/apps/auth/lldap/db/cluster.yaml`

## Step 4: Create db/kustomization.yaml

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./cluster.yaml
  - ./cnpg-externalsecret.yaml
```

## Step 5: Update the app's HelmRelease

The app needs to consume the CNPG-generated secret `<app>-pg-app` which contains `uri`, `password`, `username`, etc. Typically via:

```yaml
env:
  DATABASE_URL:
    valueFrom:
      secretKeyRef:
        name: <app>-pg-app
        key: uri
```

Or for apps that need password separately, mount or reference the individual keys.

## Step 6: Deploy and Verify

1. Commit and push, create PR, merge
2. Verify the CNPG cluster comes up: `kubectl get clusters -n <namespace>`
3. Verify the import completes (cluster status becomes `Cluster in healthy state`)
4. Verify backup completes: `kubectl get backups -n <namespace>`
5. If backups fail, check barman sidecar logs: `kubectl logs -n <namespace> -l cnpg.io/cluster=<app>-pg -c barman-cloud --tail=50`

## Step 7: Post-Migration Cleanup

Once backups are confirmed working:

1. **Switch bootstrap to recovery**: Replace `initdb.import` with `recovery.source: <app>-pg-v1`
2. **Remove source PG externalCluster entry** (the `unraid-*` one)
3. **Remove `UNRAID_PG_PASSWORD`** from the ExternalSecret (both template and data)
4. **Remove `enableSuperuserAccess` and `superuserSecret`** from the Cluster if not needed
5. **Remove the temporary firewall rule** allowing cluster → source PG

Reference for final state: `kubernetes/apps/auth/lldap/db/cluster.yaml` (after cleanup PR)

## Known Issues

- **S3 bucket must exist**: Garage does not auto-create buckets. The `cnpg` bucket must be created manually and the backup access key must have read/write/owner permissions.
- **`ClusterImageCatalog` may not exist**: Use `imageName: ghcr.io/cloudnative-pg/postgresql:17` directly instead of `imageCatalogRef`.
- **Bootstrap is only used on first creation**: Changing bootstrap after the cluster exists has no effect on the running cluster. It only matters if the cluster is recreated.
