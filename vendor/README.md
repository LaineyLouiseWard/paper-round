# vendor/

`sgmllib.py` is vendored from [sgmllib3k 1.0.0](https://pypi.org/project/sgmllib3k/)
(a Python 3 port of the standard-library `sgmllib`). `feedparser` imports it at
load time for its lenient fallback parser, but `sgmllib3k` is distributed as a
source tarball only and its build fails against the setuptools in the ephemeral
cloud-routine sandbox. Vendoring the single module lets us install feedparser with
`--no-deps` and skip the build, while keeping feedparser's tolerance of malformed
feeds (some journals emit technically invalid XML).

Do not edit. To refresh: `pip download sgmllib3k --no-binary :all:` and copy the
`sgmllib.py` it contains.
