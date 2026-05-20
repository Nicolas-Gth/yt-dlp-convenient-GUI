class ProgressLayoutMixin:
    """Mixin that provides layout utilities."""

    @staticmethod
    def _clear_layout(layout):
        """Remove and delete all items from a layout."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    ProgressLayoutMixin._clear_layout(child_layout)
            del item
