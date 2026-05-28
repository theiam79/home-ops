#!/usr/bin/env python3
import os
import sys

import jinja2


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render-talos-template.py <template-path>", file=sys.stderr)
        return 2

    template_path = sys.argv[1]
    with open(template_path) as f:
        source = f.read()

    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    sys.stdout.write(env.from_string(source).render(ENV=os.environ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
