# Historical Hermes integration patches

> **DO NOT APPLY THESE PATCHES TO CURRENT HERMES AUTOMATICALLY.**

The files in this directory are immutable provenance for earlier Darkloom integration work. They were authored against Hermes revisions thousands of commits behind the baseline now recorded in `src/darkloom/compatibility-manifest.json`.

Current compatibility is semantic:

1. pin an exact reviewed Hermes commit;
2. verify required files and source seams;
3. preserve unsupported native features;
4. retain only a narrowly proved residual Darkloom control;
5. require runtime evidence for routing claims.

Patch presence is not enforcement, and configuration is not runtime proof.
