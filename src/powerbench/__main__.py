"""Allow ``python -m powerbench`` without depending on shell activation."""

from powerbench.cli import main

raise SystemExit(main())
