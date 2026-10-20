from logfire.testing import CaptureLogfire


def finished_span_attributes(capfire: CaptureLogfire, name: str) -> list[dict]:
    return [
        {
            key: value
            for key, value in span.attributes.items()
            if not key.startswith(("logfire.", "code."))
        }
        for span in capfire.exporter.exported_spans
        if span.name == name and span.attributes["logfire.span_type"] == "span"
    ]
