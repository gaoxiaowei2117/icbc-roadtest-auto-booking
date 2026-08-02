"""Bundled entry point for the ICBC control panel exe.

Default invocation -> launch the web control panel (webui.main).
`<exe> --road <config.yml>` -> dispatch into road.main(), so the
panel can spawn the booking worker by re-invoking itself.
"""

import sys

from console_encoding import configure_utf8_output


def main() -> None:
    configure_utf8_output()
    if len(sys.argv) > 1 and sys.argv[1] == "--road":
        # Stream stdout line-buffered so the panel sees live output.
        # Rewrite argv to match road.py's argparse expectation: [prog, config_path]
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from road import main as road_main
        road_main()
        return

    from webui import main as webui_main
    webui_main()


if __name__ == "__main__":
    main()
