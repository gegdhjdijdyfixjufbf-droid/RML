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

SUPPORTED_VERSIONS = {
    "RML 0.0.1;",
    "RML 0.0.2;",
    "RML 0.0.3;",
}

COMMAND = re.compile(
    r'Create\.(title[1-6]|text|link|image)\s*'
    r'\(\s*"((?:[^"\\]|\\.)*)"\s*\)\s*'
    r'(?:at=\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*)?;',
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

INITIAL_WIDTH = 900
INITIAL_HEIGHT = 650
PAGE_MARGIN = 32


def unescape(value):
    return value.replace(r'\"', '"').replace(r'\\', '\\')


def parse_rml(filename):
    source = Path(filename).read_text(encoding="utf-8")
    lines = source.splitlines()

    if not lines or lines[0].strip() not in SUPPORTED_VERSIONS:
        raise ValueError(
            "The first line must be RML 0.0.1;, "
            "RML 0.0.2;, or RML 0.0.3;"
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
            if version not in ("RML 0.0.2;", "RML 0.0.3;"):
                raise ValueError(
                    f"Line {line_number}: SJ scripts require RML 0.0.2 or 0.0.3."
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
                ("script", (name, "\n".join(script_lines)), None)
            )
            continue

        match = COMMAND.fullmatch(line)

        if not match:
            raise ValueError(
                f"Line {line_number}: Invalid RML command:\n{line}"
            )

        command, value, x, y = match.groups()
        command = command.lower()
        value = unescape(value)

        position = None

        if x is not None:
            if version != "RML 0.0.3;":
                raise ValueError(
                    f"Line {line_number}: at=(x, y) requires RML 0.0.3."
                )

            position = (int(x), int(y))

        if command == "link":
            parsed = urlparse(value)

            if (
                parsed.scheme not in ("http", "https")
                or not parsed.netloc
            ):
                raise ValueError(
                    f"Line {line_number}: Links must use a valid "
                    "http:// or https:// URL."
                )

        elements.append((command, value, position))

    return elements


class RMLRenderer:
    def __init__(self, filename):
        self.filename = Path(filename).resolve()

        self.root = tk.Tk()
        self.root.geometry(f"{INITIAL_WIDTH}x{INITIAL_HEIGHT}")
        self.root.minsize(500, 350)
        self.root.title(f"RML Renderer — {self.filename.name}")

        self.images = []
        self.page_width = INITIAL_WIDTH
        self.page_height = INITIAL_HEIGHT

        # Main container.
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        # Vertical scrollbar.
        self.scrollbar = tk.Scrollbar(
            container,
            orient="vertical",
        )
        self.scrollbar.pack(side="right", fill="y")

        # Scrollable canvas.
        self.canvas = tk.Canvas(
            container,
            background="white",
            highlightthickness=0,
            yscrollcommand=self.scrollbar.set,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar.config(command=self.canvas.yview)

        # Page frame: placed elements do not automatically enlarge a frame,
        # so page dimensions are managed explicitly below.
        self.page = tk.Frame(
            self.canvas,
            background="white",
            width=self.page_width,
            height=self.page_height,
        )
        self.page.pack_propagate(False)

        self.page_window = self.canvas.create_window(
            0,
            0,
            anchor="nw",
            window=self.page,
            width=self.page_width,
            height=self.page_height,
        )

        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.root.bind_all(
            "<MouseWheel>",
            self.on_mousewheel,
        )

        try:
            elements = parse_rml(self.filename)
            self.render(elements)
        except (OSError, UnicodeError, ValueError) as error:
            self.show_error(str(error))

        self.update_page_size()

    def on_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(
                -int(event.delta / 120),
                "units",
            )

    def on_canvas_resize(self, event):
        # Keep the page at least as wide and tall as the visible canvas.
        self.page_width = max(self.page_width, event.width)
        self.page_height = max(self.page_height, event.height)
        self.update_page_size()

    def update_page_size(self):
        # Explicit dimensions prevent positioned widgets from being clipped
        # when the page contains no packed elements.
        self.page.configure(
            width=self.page_width,
            height=self.page_height,
        )

        self.canvas.itemconfigure(
            self.page_window,
            width=self.page_width,
            height=self.page_height,
        )

        self.canvas.configure(
            scrollregion=(
                0,
                0,
                self.page_width,
                self.page_height,
            )
        )

    def add_widget(
        self,
        widget,
        position=None,
        padx=PAGE_MARGIN,
        pady=6,
    ):
        if position is not None:
            x, y = position

            # Position is measured from the page's top-left corner.
            widget.place(x=x, y=y, anchor="nw")
            widget.update_idletasks()

            right = x + widget.winfo_reqwidth() + PAGE_MARGIN
            bottom = y + widget.winfo_reqheight() + PAGE_MARGIN

            self.page_width = max(self.page_width, right)
            self.page_height = max(self.page_height, bottom)
        else:
            # Elements without coordinates use normal vertical layout.
            widget.pack(
                anchor="w",
                fill="x",
                padx=padx,
                pady=pady,
            )

        self.update_page_size()

    def render_text(self, value, position=None):
        widget = tk.Label(
            self.page,
            text=value,
            font=("Arial", 12),
            background="white",
            foreground="#222222",
            anchor="w",
            justify="left",
            wraplength=800,
        )

        self.add_widget(widget, position)

    def render_image(self, filename, position=None):
        image_path = Path(filename)

        if not image_path.is_absolute():
            image_path = self.filename.parent / image_path

        try:
            image = tk.PhotoImage(file=str(image_path))
        except (tk.TclError, OSError) as error:
            self.show_error(
                f"Could not load image:\n{image_path}\n\n"
                f"{error}\n\nSupported formats: PNG and GIF."
            )
            return

        # Keep a reference so Tkinter does not discard the image.
        self.images.append(image)

        widget = tk.Label(
            self.page,
            image=image,
            background="white",
        )

        self.add_widget(widget, position, pady=8)

    def render(self, elements):
        for command, value, position in elements:
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

                widget = tk.Label(
                    self.page,
                    text=value,
                    font=font,
                    background="white",
                    foreground="#111111",
                    anchor="w",
                    justify="left",
                    wraplength=800,
                )

                self.add_widget(
                    widget,
                    position,
                    pady=(18, 4),
                )

            elif command == "text":
                self.render_text(value, position)

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

                self.add_widget(widget, position)

                widget.bind(
                    "<Button-1>",
                    lambda event, url=value: webbrowser.open(url),
                )

            elif command == "image":
                self.render_image(value, position)

    def show_error(self, message):
        widget = tk.Label(
            self.page,
            text="RML / SJ Error",
            font=("Arial", 24, "bold"),
            foreground="#b00020",
            background="white",
        )
        widget.pack(anchor="w", padx=24, pady=(24, 8))

        details = tk.Label(
            self.page,
            text=message,
            font=("Consolas", 11),
            foreground="#222222",
            background="white",
            justify="left",
            anchor="w",
            wraplength=800,
        )
        details.pack(anchor="w", padx=24, pady=8)

        self.page_width = max(self.page_width, 850)
        self.page_height = max(
            self.page_height,
            details.winfo_reqheight() + 100,
        )
        self.update_page_size()

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
