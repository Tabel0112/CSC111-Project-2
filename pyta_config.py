"""Macroeconomic Shock Simulator: PythonTA Configuration

This module stores the shared PythonTA configuration used by the project's
module main blocks.

Copyright and Usage Information
===============================

This file is provided solely for the personal and private use of students
taking CSC111 at the University of Toronto. All forms of distribution of this
code, whether as given or with any changes, are expressly prohibited.

This file is Copyright (c) 2026 Baiyang Chen and collaborators.
"""

PYTA_CONFIG = {
    "allowed-import-modules": [
        "__future__",
        "argparse",
        "collections.abc",
        "config",
        "country_node",
        "csv",
        "dash",
        "data_parser",
        "dataclasses",
        "doctest",
        "graph_builder",
        "logging",
        "pathlib",
        "plotly.graph_objects",
        "python_ta",
        "pyta_config",
        "runtime_options",
        "simulation",
        "socket",
        "threading",
        "typing",
        "utils",
        "visualization",
        "webbrowser",
    ],
    "disable": [
        "too-many-instance-attributes",
        "too-many-arguments",
        "too-many-locals",
        "import-outside-toplevel",
        "naming-convention-violation",
    ],
    "max-line-length": 120,
}


if __name__ == "__main__":
    import doctest
    import python_ta

    doctest.testmod()
    python_ta.check_all()
