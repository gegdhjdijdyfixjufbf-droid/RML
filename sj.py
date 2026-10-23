
import re


class SJ:
    def __init__(self, output):
        self.output = output

    def run(self, code):
        for number, line in enumerate(code.splitlines(), start=1):
            line = line.strip()

            if not line or line.startswith("//"):
                continue

            match = re.fullmatch(
                r'Display\.Text\s*\(\s*("(?:[^"\\]|\\.)*")\s*\)\s*;',
                line,
            )

            if not match:
                raise ValueError(
                    f"SJ line {number}: Invalid command:\n{line}"
                )

            value = match.group(1)[1:-1]
            value = value.replace(r'\"', '"').replace(r'\\', '\\')
            self.output(value)
