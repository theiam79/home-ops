# external-secrets

External Secrets Operator with the Bitwarden Secrets Manager provider. The
controller talks to `bitwarden-sdk-server` over TLS; that connection is secured
by a small internal PKI defined in `app/certificate.yaml`:

1. `bitwarden-bootstrap-issuer` (self-signed) issues `bitwarden-bootstrap-certificate`,
   a CA stored in the `bitwarden-ca-certs` secret.
2. `bitwarden-certificate-issuer` (CA issuer backed by `bitwarden-ca-certs`) issues
   the serving cert `bitwarden-tls-certs` for the sdk-server.
3. The `ClusterSecretStore` trusts the CA via `caProvider` → `bitwarden-ca-certs/ca.crt`.

## Why the CA is 10-year / `rotationPolicy: Never`

With cert-manager defaults (90d duration, renew at 60d, key rotation on renewal
since cert-manager 1.18), the CA re-keys every 60 days. The leaf is only
reissued on *its own* schedule, so after every CA renewal the leaf is signed by
the **old** CA key while the `caProvider` bundle holds only the **new** CA —
every ExternalSecret fails with:

```
tls: failed to verify certificate: x509: certificate signed by unknown authority
(candidate authority certificate "cert-manager-bitwarden-tls")
```

This broke the cluster twice (2026-06 expired-CA variant, 2026-07-13 rotation
variant, both = all 77 ExternalSecrets down, dependent Flux ks failing).

Fix: the CA uses `duration: 87600h` (10y) and `privateKey.rotationPolicy: Never`.
A stable CA key means leaf renewals (still 90d/60d defaults) always chain to the
trusted bundle, and even a far-future CA renewal reuses the same key so old
leafs keep verifying. Leaf renewals are picked up automatically: the sdk-server
pod carries `secret.reloader.stakater.com/reload: bitwarden,bitwarden-tls-certs`
(set via `podAnnotations` in `app/helm/values.yaml`), and reloader restarts it
when the serving cert changes (verified working 2026-07-13).

## Runbook: `ExternalSecretNotSynced` firing cluster-wide

Cluster-wide (not per-app) failure almost always means the CA/leaf chain broke:

```sh
# Compare serials: leaf issuer vs CA bundle
kubectl get secret -n external-secrets bitwarden-tls-certs -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -issuer -serial -dates
kubectl get secret -n external-secrets bitwarden-ca-certs -o jsonpath='{.data.ca\.crt}' \
  | base64 -d | openssl x509 -noout -subject -serial -dates

# If they don't chain: reissue the leaf against the current CA
cmctl renew bitwarden-tls-certs -n external-secrets
# reloader restarts bitwarden-sdk-server automatically once the secret updates

# Speed up recovery (otherwise ExternalSecrets retry on backoff):
kubectl get externalsecret -A -o json \
  | jq -r '.items[] | select(.status.conditions[0].status != "True")
           | "\(.metadata.namespace)/\(.metadata.name)"' \
  | while IFS=/ read -r ns name; do
      kubectl annotate externalsecret -n "$ns" "$name" --overwrite force-sync="$(date +%s)"
    done
```

Then reconcile any Flux Kustomizations stuck on `HealthCheckFailed`/`DependencyNotReady`.
