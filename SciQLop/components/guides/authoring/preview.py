"""Freeze a guide at chosen moments, as Qt will play it inside SciQLop, and save a light and a dark sheet.

    python -m SciQLop.components.guides.authoring.preview guide.svg --times 0.4 2.3 7.2 --out /some/dir/sheet

writes /some/dir/sheet-light.png and sheet-dark.png, and fails when Qt would not animate the file.
Look at both: nobody can judge an animation from its source.
"""
import argparse
import os
import sys
from pathlib import Path


def tokens_of(declarations: str) -> dict[str, str]:
    return dict(item.split(":", 1) for item in declarations.strip(";").split(";"))


def render(svg: str, times: list[float], tokens: dict[str, str], target: str, columns: int) -> None:
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from SciQLop.components.guides.qt_svg import for_qt
    renderer = QSvgRenderer(QByteArray(for_qt(svg, tokens).encode()))
    if not renderer.isValid() or not renderer.animated():
        sys.exit("Qt does not animate this file: look for a CSS variable left unresolved, an @media block, "
                 "or keyframe stops grouped as '0%, 5% { }'.")
    width, height = 720, 430
    sheet = QImage(width * columns, height * -(-len(times) // columns), QImage.Format.Format_ARGB32)
    sheet.fill(QColor(tokens["--bar"]))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, seconds in enumerate(times):
        renderer.setCurrentFrame(int(seconds * renderer.framesPerSecond()))
        renderer.render(painter, QRectF((i % columns) * width, (i // columns) * height, width, height))
    painter.end()
    sheet.save(target)
    print(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--times", type=float, nargs="+", required=True, help="seconds into the loop")
    parser.add_argument("--out", required=True, help="output prefix, without -light.png")
    parser.add_argument("--cols", type=int, default=3)
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from SciQLop.components.guides.authoring import kit
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    svg = args.svg.read_text(encoding="utf-8")
    for theme, declarations in (("light", kit.LIGHT), ("dark", kit.DARK)):
        render(svg, args.times, tokens_of(declarations), f"{args.out}-{theme}.png", args.cols)
    del app


if __name__ == "__main__":
    main()
