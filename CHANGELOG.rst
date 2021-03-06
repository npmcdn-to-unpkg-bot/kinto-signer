Changelog
=========

This document describes changes between each past release.

0.9.0 (unreleased)
------------------

- Nothing changed yet.


0.8.1 (2016-08-26)
------------------

**Bug fixes**

- Warn if the storage backend timezone is not configured to use UTC (#122)
- Fix signing when all records have been deleted from the source (#120)


0.8.0 (2016-08-23)
------------------

Now requires *kinto >= 3.3*.

**New features**

- The API can now rely on a workflow and can check that users changing collection status
  belong to some groups (e.g. ``editors``, ``reviewers``).
- When a change is made in the source collection, its status is switched to
  ``work-in-progress``
- When a collection is modified, the ``last-author`` attribute is set to the current userid.
  When set to ``to-review``, the ``last_editor`` value is set, and when set to ``to-sign``
  the ``last_reviewer`` value is set.

**Bug fixes**

- Fix crash when several collections are created with status: to-sign using
  a batch request (fixes #116)


0.7.3 (2016-07-27)
------------------

**Bug fixes**

- Fix signature inconsistency (timestamp) when several changes are sent from
  the *source* to the *destination* collection.
  Fixed ``e2e.py`` and ``validate_signature.py`` scripts (fixes #110)

**Minor change**

- Add the plugin version in the capability. (#108)

0.7.2 (2016-07-25)
------------------

**Bug fixes**

- Provide the ``old`` value on destination records updates (#104)
- Send ``create`` event when destination record does not exist yet.
- Events sent by kinto-signer for created/updated/deleted objects in destination now show
  user_id as ``plugin:kinto-signer``

0.7.1 (2016-07-21)
------------------

*kinto-signer* now requires bug fixes that were released in Kinto 3.2.4 and Kinto 3.3.2.

**Bug fix**

- Update the `last_modified` value when updating the collection status and signature (#97)
- Prevents crash with events on ``default`` bucket on Kinto < 3.3
- Trigger ``ResourceChanged`` events when the destination collection and records are updated
  during signing. This allows plugins like ``kinto-changes`` and ``kinto.plugins.history``
  to catch the changes (#101).


0.7.0 (2016-06-28)
------------------

**Breaking changes**

- The collection timestamp is now included in the payload prior to signing.
  Old clients won't be able to verify the signature made by this version.

**New features**

- Raise configuration errors if resources are not configured correctly (ref #88)


0.6.0 (2016-05-19)
------------------

- Update to ``kinto.core`` for compatibility with Kinto 3.0. This
  release is no longer compatible with Kinto < 3.0, please upgrade!


0.5.0 (2016-05-17)
------------------

**Bug fix**

- Do not crash on record deletion if destination was never synced (#82)

**Internal changes**

- Rename ``get_local_records`` to ``get_source_records`` (#83)
- Rename ``sign_and_update_remote`` to ``sign_and_update_destination`` (#85)


0.4.0 (2016-05-10)
------------------

**New features**

- Ability to define a different signer per collection (#52)

**Bug fix**

- Return 503 instead of 500 when signing fails (fixes #71)

**Internal changes**

- Removed scary diagram with Mozilla specific stuff (#60)


0.3.0 (2016-04-26)
------------------

**Breaking changes**

- Change the format of exposed settings in the root URL capabilities (fixes #63)
- The ``hook.py`` module was deleted, meaning that if ``kinto_signer.hook`` was
  used in ``kinto.includes`` setting, it will break.
  Use ``kinto.includes = kinto_signer`` instead.
- Switch to ``Content-Signature`` spec, as by provided Autograph and expected
  by Firefox Personal Security Manager.
  Mainly means that ``Content-Signature:\x00`` has to be prepended to payload
  prior to signing verification.

**New features**

- Add signer entry in heartbeat view (fixes #50)
- Change the source/destination settings format (fixes #35). Old format is still
  supported.

**Internal changes**

- Fix test coverage for resource event (#59)
- Add more tests for canonical JSON serializers (#58)
- Add a end-to-end smoke script to be ran on a Kinto instance (#64)

0.2.0 (2016-03-22)
------------------

- Update autograph to version 1.1.0


0.1.0 (2016-03-07)
-------------------

- Provide a hook that triggers a signature on the current local collection and
  replicate it to the destination collection.
- Provide a local ECDSA signer.
- Provide a remote Autograph signer.
- Handle addition and deletion of records during the replication.
- Support multiple source and destination resources
