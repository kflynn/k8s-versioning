```bash
set -e

if ! command -v kubectl-edit_status >/dev/null 2>&1; then \
    echo "Please install kubectl-edit_status from https://github.com/ulucinar/kubectl-edit-status" >&2 ;\
    exit 1 ;\
fi

set +e
```

<!-- @SHOW -->

Assume we have an empty cluster.

Create FFS version v1alpha1:

```bash
kubectl apply -f ffs-a1.yaml
```

...then create some v1a1 CRDs.

```bash
kubectl apply -f good-a1.yaml

# This should show
# NAME     FFS   STRENGTH
# hex-a1   hex
# pox-a1   pox   4
kubectl get ffs
```

There's a field in the CRD status that tells us what versions are stored.
Right now, it (correctly) shows that we have v1alpha1 CRs and that's it --
after all, we haven't defined any other versions.

```bash
kubectl get crd ffses.kodachi.com -o jsonpath='{range .status.storedVersions[*]}{@}{"\n"}{end}'
```

Now, create FFS version v1alpha2, without doing anything to v1alpha1. The
difference between the two versions is that v1alpha2 has a `curse` field
instead of `ffs`.

```bash
kubectl apply -f ffs-a1a2.yaml
```

Fascinatingly enough, the APIServer _instantly_ declares that we have v1alpha2
CRs stored now -- even though we haven't created any v1alpha2 CRs yet.

```bash
kubectl get crd ffses.kodachi.com -o jsonpath='{range .status.storedVersions[*]}{@}{"\n"}{end}'
```

However, `kubectl` will still be using v1alpha1 CRs by default.

```bash
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
kubectl get ffs
```

This default version lives in the local information that `kubectl` caches.
`kubectl api-resources`, you'll note, has already switched to v1alpha2.

```bash
kubectl api-resources | grep ffs
```

...and as soon as we do _that_, we'll find that `kubectl` has switched to
v1alpha2, because it cached the information from the APIServer it just fetched
from the APIServer.

```bash
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
# This should show
# NAME     CURSE  STRENGTH
# hex-a1
# pox-a1          4
kubectl get ffs
```

_Anything_ that results in `kubectl` re-requesting API resources from the
APIServer will switch `kubectl`'s default version to v1alpha2. OTOH, a
controller won't land in this situation, because the controller has to be
explicit about what version it wants to use.

<!-- @wait -->

Now, create some v1alpha2 CRs.

```bash
kubectl apply -f good-a2.yaml
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
# NAME          CURSE      STRENGTH
# hex-a1
# pox-a1                   4
# darkness-a2   darkness   2
# hex-a2        hex        2
kubectl get ffs
```

We can still request v1alpha1 CRs explicitly, and doing that will cause
`kubectl` to use the printer columns from v1alpha1 as well.

```bash
# NAME          FFS   STRENGTH
# hex-a1        hex
# pox-a1        pox   4
# darkness-a2         2
# hex-a2              2
kubectl get ffs.v1alpha1.kodachi.com
```

Note that the APIServer is returning all the fields that are actually present
in the CRs, though.

```bash
kubectl get ffs.v1alpha1.kodachi.com -o jsonpath='{range .items[*]}{.apiVersion}{": "}{.spec}{"\n"}{end}'
kubectl get ffs.v1alpha2.kodachi.com -o jsonpath='{range .items[*]}{.apiVersion}{": "}{.spec}{"\n"}{end}'
```

This permits us to do a simple upgrade-in-place of our v1alpha1 CRs:

```bash
kubectl get ffs -o yaml | python convert-a1a2.py | kubectl apply -f -
kubectl get ffs
kubectl get ffs.v1alpha1.kodachi.com
kubectl get ffs.v1alpha1.kodachi.com -o jsonpath='{range .items[*]}{.apiVersion}{": "}{.spec}{"\n"}{end}'
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{": "}{.spec}{"\n"}{end}'
```

At this point, if we try to delete v1alpha1 by applying a CRD with v1alpha2
and v1, the APIServer will refuse to delete the v1alpha1 CRs, because it still
thinks it has some v1alpha1 CRs stored.

```bash
kubectl apply -f ffs-a2v1.yaml
kubectl get crd ffses.kodachi.com -o jsonpath='{range .status.storedVersions[*]}{@}{"\n"}{end}'
```

We know that we've converted all the CRs to v1alpha2, so we can safely delete
the storedVersion. We'll use the (very overly simple) `strip-v1a1.sh` script
as an editor for `kubectl edit-status` to do this (because, of course, you
can't just `kubectl edit` the status field...).

```bash
kubectl edit-status --editor=$(pwd)/strip-v1a1.sh crd ffses.kodachi.com
kubectl get crd ffses.kodachi.com -o jsonpath='{range .status.storedVersions[*]}{@}{"\n"}{end}'
```

At this point, we can drop the v1alpha1 version, which we'll do as we add the
v1 version.

```bash
kubectl apply -f ffs-a2v1.yaml
```

Again, `kubectl` will still request v1alpha2 CRs by default, until we mention
v1 to the APIServer.

```bash
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
kubectl get ffs.v1.kodachi.com -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
kubectl get ffs -o jsonpath='{range .items[*]}{.apiVersion}{"\n"}{end}'
```

(Creating a v1 CR, of course, would count as mentioning v1 to the APIServer.)

