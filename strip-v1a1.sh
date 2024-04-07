#!/bin/sh

# This is a dirt simple script to be used as an "editor" for kubectl
# edit-status. It will be called with a single argument, which is a path to
# the YAML to edit. It needs to remove the v1alpha1 API version from the
# storedVersions field in the status subresource, updating the file in place.
#
# As it happens, the only place '  - v1alpha1' appears in the file as a line
# by itself is in the storedVersions field, so we'll do this with egrep.
egrep -v '^  - v1alpha1$' < "$1" > "$1.tmp"
mv "$1.tmp" "$1"
