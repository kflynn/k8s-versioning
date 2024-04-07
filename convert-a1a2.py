import sys
import yaml

# This is simple Python program that reads a list of Custom Resources (CRs)
# from stdin and converts any FFS CRs in the kodachi.com APIGroup that have an
# 'ffs' field to the v1alpha2 APIGroup, which uses the 'curse' field instead.
#
# Note that we can't actually key on the stored version, because the APIServer
# won't tell us what's really stored! So we have to use the presence of the
# 'ffs' field to determine if it needs to be converted.

crs = yaml.safe_load(sys.stdin)
updates = []

for cr in crs['items']:
    apiVersion = cr['apiVersion']
    kind = cr['kind']
    name = cr['metadata']['name']
    namespace = cr['metadata']['namespace']
    spec = cr['spec']
    ffs = spec.get('ffs', None)

    # sys.stderr.write(f'Checking {name} in {namespace}: {apiVersion}\n')
    if (apiVersion.startswith('kodachi.com')
        and (kind == 'FFS')
        and (ffs is not None)):
        cr2 = {
            'apiVersion': 'kodachi.com/v1alpha2',
            'kind': 'FFS',
            'metadata': {
                'name': name,
                'namespace': namespace,
            },
            'spec': spec.copy(),
        }

        cr2['spec']['curse'] = ffs
        del cr2['spec']['ffs']
        updates.append(cr2)

        sys.stderr.write(f'Updated {name} in {namespace}\n')

for cr in updates:
    print('---')
    print(yaml.dump(cr, default_flow_style=False))
