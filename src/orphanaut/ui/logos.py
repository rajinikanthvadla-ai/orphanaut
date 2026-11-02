"""Cloud provider logos as inline SVG, rendered with QtSvg."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from orphanaut.models import CloudProvider

AWS_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 40">
  <text x="32" y="22" text-anchor="middle" font-family="Arial, Helvetica, sans-serif"
        font-weight="700" font-size="22" fill="#232F3E">aws</text>
  <path d="M9 28 Q32 39 53 28" fill="none" stroke="#FF9900" stroke-width="3.6"
        stroke-linecap="round"/>
  <path d="M46.5 25.8 L54.5 27.4 L51.6 34.6" fill="none" stroke="#FF9900" stroke-width="3.4"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

AZURE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
  <defs>
    <linearGradient id="a" x1="58.97" y1="9.68" x2="31.36" y2="91.25"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#114A8B"/><stop offset="1" stop-color="#0669BC"/>
    </linearGradient>
    <linearGradient id="b" x1="46.09" y1="9.68" x2="76.39" y2="90.4"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#3CCBF4"/><stop offset="1" stop-color="#2892DF"/>
    </linearGradient>
  </defs>
  <path fill="url(#a)" d="M33.34 6.54h26.04L32.36 86.66a4.15 4.15 0 0 1-3.94 2.82H8.15a4.15
    4.15 0 0 1-3.93-5.48L29.4 9.36a4.15 4.15 0 0 1 3.94-2.82z"/>
  <path fill="#0078D4" d="M71.17 60.26H29.88a1.91 1.91 0 0 0-1.3 3.31l26.53 24.76a4.17 4.17 0
    0 0 2.85 1.12h23.38z"/>
  <path fill="url(#b)" d="M66.6 9.36a4.15 4.15 0 0 0-3.93-2.82H33.65a4.15 4.15 0 0 1 3.93
    2.82l25.18 74.62a4.15 4.15 0 0 1-3.93 5.48h29.02a4.15 4.15 0 0 0 3.93-5.48z"/>
</svg>
"""

GCP_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 52">
  <g fill="none" stroke-width="6.5">
    <path d="M14.5 26.5 A17 17 0 0 1 46 18.5" stroke="#EA4335"/>
    <path d="M46 18.5 A12.5 12.5 0 0 1 47 45 L35 45" stroke="#4285F4"/>
    <path d="M35 45 L19 45" stroke="#34A853"/>
    <path d="M19 45 A9.5 9.5 0 0 1 14.5 26.5" stroke="#FBBC05"/>
  </g>
</svg>
"""

_SVGS = {CloudProvider.AWS: AWS_SVG, CloudProvider.AZURE: AZURE_SVG, CloudProvider.GCP: GCP_SVG}


def render_logo(provider: CloudProvider, width: int, height: int) -> QPixmap:
    """Logo centred in a transparent width x height pixmap, keeping its aspect ratio."""
    renderer = QSvgRenderer(QByteArray(_SVGS[provider].encode()))
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    box = renderer.viewBoxF()
    scale = min(width / box.width(), height / box.height())
    w, h = box.width() * scale, box.height() * scale
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF((width - w) / 2, (height - h) / 2, w, h))
    painter.end()
    return pixmap
