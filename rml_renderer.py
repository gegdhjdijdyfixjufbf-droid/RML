import tkinter
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from sj import SJ

ROOT = Path(__file__).resolve().parent

COMMAND = re.compile(
    r'Create\.(title[1-6]|text|link|image)\s*'
    r'\(\s*"((?:[^"\\]|\\.)*)"\s*\)\s*;',
    re.IGNORECASE,
)

SCRIPT_START = re.compile(
    r'Create\.script\s+name=\("([^"]+)"\)',
    re.IGNORECASE,
)

TITLE_SIZES = {
    "title1": 36,
    "title2": 30,
    "title3": 25,
    "title4": 21,
    "title5": 18,
    "title6": 15,
}


def unescape(value):
    return value.replace(r'\"', '"').replace(r'\\', '\\')


def parse_rml(filename):
    source = Path(filename).read_text(encoding="utf-8")
    lines = source.splitlines()

    if not lines or lines[0].strip() not in (
        "RML 0.0.1;",
        "RML 0.0.2;",
    ):
        raise ValueError(
            "First line must be RML 0.0.1; or RML 0.0.2;"
        )

    version = lines[0].strip()
    elements = []
    i = 1

    while i < len(lines):
        line_number = i + 1
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("//"):
            continue

        script_match = SCRIPT_START.fullmatch(line)

        if script_match:
            if version != "RML 0.0.2;":
                raise ValueError(
                    f"Line {line_number}: Scripts require RML 0.0.2."
                )

            name = script_match.group(1)
            script_lines = []

            while i < len(lines):
                script_line = lines[i].strip()

                if not script_line or script_line.startswith("//"):
                    i += 1
                    continue

                if script_line.startswith("Create."):
                    break

                script_lines.append(script_line)
                i += 1

            elements.append(
                ("script", (name, "\n".join(script_lines)))
            )
            continue

        match = COMMAND.fullmatch(line)

        if not match:
            raise ValueError(
                f"Line {line_number}: Invalid RML command:\n{line}"
            )

        command, value = match.groups()
        command = command.lower()
        value = unescape(value)

        if command == "link":
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"Line {line_number}: Link must be a valid "
                    "http:// or https:// URL."
                )

        elements.append((command, value))

    return elements


class RMLRenderer:
    def __init__(self, filename):
        self.root = tk.Tk()
        self.root.geometry("900x650")
        self.root.minsize(500, 350)

        self.filename = Path(filename).resolve()
        self.root.title(f"RML Renderer — {self.filename.name}")

        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(
            container,
            background="white",
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.canvas.yview)

        self.page = tk.Frame(self.canvas, background="white")
        self.page_window = self.canvas.create_window(
            0, 0, anchor="nw", window=self.page
        )

        self.images = []

        self.page.bind(
            "<Configure>",
            lambda event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )

        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(
                self.page_window, width=event.width
            ),
        )

        self.root.bind_all(
            "<MouseWheel>",
            lambda event: self.canvas.yview_scroll(
                -int(event.delta / 120), "units"
            ),
        )

        try:
            self.render(parse_rml(self.filename))
        except (OSError, UnicodeError, ValueError) as error:
            self.show_error(str(error))

    def render_text(self, value):
        tk.Label(
            self.page,
            text=value,
            font=("Arial", 12),
            background="white",
            foreground="#222222",
            anchor="w",
            justify="left",
            wraplength=800,
        ).pack(
            anchor="w",
            fill="x",
            padx=32,
            pady=6,
        )

    def render_image(self, filename):
        image_path = Path(filename)

        if not image_path.is_absolute():
            image_path = self.filename.parent / image_path

        try:
            image = tk.PhotoImage(file=str(image_path))
        except (tk.TclError, OSError) as error:
            self.show_error(
                f"Could not load image:\n{image_path}\n\n{error}\n\n"
                "Supported formats: PNG and GIF."
            )
            return

        self.images.append(image)

        tk.Label(
            self.page,
            image=image,
            background="white",
        ).pack(anchor="w", padx=32, pady=8)

    def render(self, elements):
        for command, value in elements:
            if command == "script":
                name, code = value
                try:
                    SJ(self.render_text).run(code)
                except Exception as error:
                    self.show_error(
                        f"SJ script '{name}' failed:\n{error}"
                    )

            elif command.startswith("title"):
                font = tkfont.Font(
                    family="Arial",
                    size=TITLE_SIZES[command],
                    weight="bold",
                )

                tk.Label(
                    self.page,
                    text=value,
                    font=font,
                    background="white",
                    foreground="#111111",
                    anchor="w",
                    justify="left",
                    wraplength=800,
                ).pack(
                    anchor="w",
                    fill="x",
                    padx=32,
                    pady=(18, 4),
                )

            elif command == "text":
                self.render_text(value)

            elif command == "link":
                widget = tk.Label(
                    self.page,
                    text=value,
                    font=("Arial", 12, "underline"),
                    background="white",
                    foreground="#0759c7",
                    cursor="hand2",
                    anchor="w",
                    justify="left",
                    wraplength=800,
                )
                widget.pack(
                    anchor="w",
                    fill="x",
                    padx=32,
                    pady=6,
                )
                widget.bind(
                    "<Button-1>",
                    lambda event, url=value: webbrowser.open(url),
                )

            elif command == "image":
                self.render_image(value)

    def show_error(self, message):
        tk.Label(
            self.page,
            text="RML / SJ Error",
            font=("Arial", 24, "bold"),
            fg="#b00020",
            bg="white",
        ).pack(anchor="w", padx=24, pady=(24, 8))

        tk.Label(
            self.page,
            text=message,
            font=("Consolas", 11),
            fg="#222222",
            bg="white",
            justify="left",
            anchor="w",
            wraplength=800,
        ).pack(anchor="w", padx=24, pady=8)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    filename = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "index.rml"
    )

    if not filename.is_absolute():
        filename = ROOT / filename

    RMLRenderer(filename).run()
