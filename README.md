# API Versioning

Kubernetes does not make versioning APIs easy.

The most common guidance we hear pretty much boils down "you can't remove
anything and you can't ever go backward", which is troubling in the real
world. For Gateway API it's a _serious_ problem, because Gateway API's
experimental channel needs to be allowed to introduce things that can turn out
to be not ready for prime time, and therefore aren't included in the standard
channel.

The most obvious reason that this is troubling is that if you're writing code
that uses the experimental channel, and then the features you're using make it
into standard, you'll need a way to migrate to standard channel, and that will
involve removing fields and API versions.

Additionally, though, experimental fields in a CRD may need to be
removed or renamed while still in experimental... and while we'll have alpha versions in experimental that won't be in standard, we won't always have version changes in the experimental channel every time we make a change.

Weirdly, both of these turn out to be less of a problem than they first
appear, because the APIServer doesn't actually version CRDs at all. What it
versions is _its presentation of CRs to you_.

## The Lying Ways the APIServer Lies to Us

What's actually stored in the APIServer for a CR is a bunch of fields and their values. The APIServer seems to not care in the slightest what fields are actually stored for a given CR.

(Running `demosh DEMO.md` will show some of this in action.)

### CRs Are Not Actually Versioned in Storage

One of the fields we have for CRs is called `apiVersion`, and we need to take
that literally. `apiVersion` refers to the version of the CRD that identified
the rules that the APIServer was using while processing your request. It _does
not_ refer to versioning in storage; the APIServer doesn't seem to have any
actual concept of versioning in storage. It just has a bunch of fields and
values that it associates with a given CR.

This means that if you use `v1alpha1` to create a CR, the APIServer will do
validation of the input resource using the rules described by `v1alpha1` in
the CRD... but if you then turn around and use `v1alpha2` when requesting that
CR, the APIServer will use the `v1alpha2` rules to decide what fields to send, and `kubectl` will use the presentation rules described by `v1alpha2` to show
you the CR. Nothing has changed about what's stored in the APIServer.

### The APIServer _Will Not_ Ever Tell You What Version is Stored

This is because the APIServer doesn't seem to have a concept of storage
version, so how _could_ it tell you this? Instead, `apiVersion` in its
responses correctly identifies the version of the API that was used to process
the request.

(Modifying the APIServer to keep track of the API version used the most recent
time the CR was updated is intriguing, and might be helpful -- but not in any
short term.)

### The APIServer Claims to Track Stored Versions, but Lies

There's a field in the CRD status called `storedVersions`, which implies that
it's tracking which versions have CRs stored. Nope, it's really versions that
are _defined_ for a given CRD: creating a new version immediately updates
"storedVersions", even though you haven't had a chance to create any CRs of
that version yet.

The only way to remove a version from `storedVersions` is to update the CRD
status manually.

### The APIServer _Will Not_ Allow You to Delete a Stored Version

If a version appears in `storedVersions`, you won't be able to delete that
version from the CRD. This isn't because the APIServer cares what versions are
stored (it doesn't know), but until you delete the version from
`storedVersions`, it figures you probably still have software that will try to
make requests using that version.

### The APIServer _Will_ Allow Marking a Stored Version as Not Served

On the other hand, if you do this, the server will respond to requests for that version with an error that's indistinguishable from the error you get if you request a version that doesn't exist. This is probably best viewed as a final step before deleting a version from `storedVersions`: you can mark it as not served, then wait a while to see if anything breaks.

### The APIServer _Cannot_ Prevent Writes to a Served Version

On the face of it, this seems like a good thing to change, but ultimately, no,
I think it has to be this way. If you could stop writes, you effectively force
any users of that version to migrate to a new version. This is a problem if
you have a lot of users and you're not sure they're all ready to migrate.

### The APIServer _Can_ Deliver Everything That Is Stored

If a given CRD version sets `x-kubernetes-preserve-unknown-fields` to true, then the APIServer will always send all the fields in storage for a given CR, irrespective of what the requested version implies about which fields are actually supposed to be present.

This fact means that you can write a conversion utility that does not rely on
conversion webhooks: you can just grab all the fields stored for the old
version, do whatever updates you need to do, then write a CR with the same
name and the new version -- as long as you can infer what changes are needed
without knowing what version is actually stored.

Of course, wihout `x-kubernetes-preserve-unknown-fields`, the APIServer will drop any fields that are unknown in the version you requested, which means that you MUST set `x-kubernetes-preserve-unknown-fields` to true if you don't want to rely on conversion webhooks.

### The APIServer _Can_ Honor Whatever Version You Request

Requests made to the APIServer _must_ specify a version. `kubectl` hides this
by trying very hard to keep track of the latest version for you, behind the
scenes, but if you're writing a controller, you have to be explicit about what
version you want to use.

## Guidelines

Given all that... what do we do about it?

### Definitions

**Version**: A set of fields with a specific set of semantics. This is _very different_ from a Kubernetes `apiVersion`. If you change the semantics of a field, that's a new "version" here, whether or not you change the `apiVersion`.

The reason for this is that the APIServer doesn't actually version CRs in
storage, so talking about `apiVersion` as a versioning specification isn't
meaningful.

**Additive Change**: A change between versions where the only difference is adding a new field.

**Semantic Breaking Change**: A change between versions that breaks the
semantics of a given field: either you're removing a field, changing its name,
or changing what it means.

**API Designer**: Anyone defining what an API _means_.

**Implementer**: Anyone writing code that uses the API.

**Consumer**: Anyone using the API in any way (for example, a Gateway
implementer is a consumer of the HTTPRoute API, but so is an end user trying
to use HTTPRoutes to configure a Gateway).

### DO Use Semantic Versioning for CRDs

Obviously Kubernetes won't know anything about this, but **API designers
SHOULD use semantic version numbers _somewhere_ as a way of communicating the
level of risk in a version change to consumers.**

Purely additive changes SHOULD change the patch version. Semantic breaking
changes SHOULD probably be minor version changes, depending on the severity of
the change. Major version changes SHOULD be reserved for changes that drop
entire resources or change the meaning of the resource in a fundamental way.

Again, Kubernetes cannot use this version; this is for human communication.

### DO Avoid Semantic Breaking Changes Whenever Possible

Additive changes are no big deal. Code using old versions won't expect the new
field, won't look for it, and won't break if it's present.

Semantic breaking changes _are_ a big deal. **Designers SHOULD avoid semantic
breaking changes whenever possible**, though of course there are times
(especially in Gateway API experimental) where avoiding them is worse than
allowing them.

### DON'T Design Using Conversion Webhooks

On the face of it, conversion webhooks seem to offer a great way to handle
semantic breaking changes. Unfortunately, they turn out to be an operational
nightmare. **API designers MUST NOT use conversion webhooks.**

### DO Design Using `x-kubernetes-preserve-unknown-fields`

This is the only way to ensure that you can write a conversion utility that
doesn't rely on conversion webhooks.

**API designers MUST set `x-kubernetes-preserve-unknown-fields` to true for
each version defined in a CRD.**

### DO Define Conversion When Changing the API

**Designers MUST define how controllers should manage conversion for every
semantic breaking change.** This is a requirement both for writing conversion
utilities and for writing controllers that can support more than one version,
and it's not something to be left up to the implementer absent guidance.

The designer knows what the change is, and can define how to handle it. The
APIServer can't help here, either, since it doesn't do versioned storage.

Example: BackendTLSPolicy.TLS is going to be renamed as BackendTLSPolicy.Validation. The conversion is:

- If you see a BackendTLSPolicy that has a TLS field, copy the value to the
  Validation field and remove the TLS field. _(I didn't say it was a very
  profound conversion...)_

#### Corollary: If You Can't Define the Conversion, Don't Make the Change

**API designers MUST NOT make changes that can't be converted without knowing
the stored version.** This is a recipe for disaster, because _nothing_ that
Kubernetes can do can reveal the change.

(Note that it is _possible_ to add a new field that is required by validation
to have a specific value, and then to use that new field as a stored version
key. Since this really isn't of any value to the user, I'm not going to
consider.)

#### Corollary: Conversions Need to be Bidirectional Within Experimental

**API designers MUST define bidirectional conversions for semantic breaking
changes within the experimental channel.** This is a requirement to allow
deciding that a given semantic breaking change was a bad idea and needs to be
rolled back.

This implies that merging fields should be viewed with extra skepticism, and
may require extra fields to be preserved in the new version to allow for the
reverse conversion.

For BackendTLSPolicy.Validation, the reverse conversion is simple:

- If you see a BackendTLSPolicy that has a Validation field, copy the value to
  the TLS field and remove the Validation field.

**API designers SHOULD define bidirectional conversions for semantic breaking changes between experimental and stable**, but Gateway API SHOULD NOT accept a change into stable without amble evidence that it is acceptable.

### DO Implement Using the Latest Version At The Time of Implementation

**Implementers SHOULD use the latest version of the CRD that's available at
the time of implementing.** There's no point in writing code that's guaranteed
to require changes even while you're writing it.

### DO Consider Whether Supporting Old Versions is Valuable

**Implementers MAY choose to not support old versions of a CRD at all.** In
many cases, there may be no point: if you're writing new code for a user
community that hasn't ever used any older versions, why bother?

### DO Implement Canonicalization, but DON'T Change CR Spec Stanzas

When writing a controller, assume that the CRs you see may have been defined
using older API versions, with semantics different from whatever version your
controller considers "native". **Implementers MUST do whatever is required to
adapt received CRs to their current version, but MUST NOT change the CRs
themselves.**

#### Corollary: Canonicalize Older to Newer, not Newer to Older

**Implementers MUST ignore CRs that don't fit a version that their controller
supports.** In general, your controller cannot understand a CR version created
after your controller was written; don't try to force the issue.

## Where Does This Leave Us?

The major points in the guidelines are:

- The `apiVersion` isn't actually a meaningful version for a CRD, so we have
  to think about versioning differently. This is actually not a new problem,
  though it's one that I don't think has been communicated well in the
  Kubernetes world.

- Semantic breaking changes are expensive, and must come with definitions of
  how to convert from the old version to the new.

   - If every semantic breaking change includes the conversion definition,
     it's always possible to convert older resources to newer resources,
     allowing dropping the older version.

   - If the conversion is bidirectional, it's possible to roll back a semantic
     breaking change if we realize that it's a bad idea.

   - If every semantic breaking change includes the conversion definition,
     it's possible to convert from experimental to stable and then remove the experimental definitions.

- Implementers are going to need to be prepared to canonicalize versions
  internally. This sounds worse than it is: working with multiple versions
  tends to require this, in some form, in general.

- The API designers have to do more work in the form of defining conversions.
  There's no way around this, and it's annoying, but it's the only way to
  ensure that the API can actually evolve.

- For Gateway API in particular, we can actually build this in to the process.
  Other APIs should do the same.

- We should think hard about whether there's a way that the APIServer can
  provide more assistance with this stuff. It's not like it's going to get any
  easier.