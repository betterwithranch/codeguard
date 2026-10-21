from collections.abc import Mapping
from dataclasses import dataclass

from vulture import Vulture
from vulture.core import Item

from codeguard.dead_code.definition_usage import DefinitionKey, DefinitionUsage, UnusedDefinition


@dataclass(frozen=True)
class VultureEngine:
    whitelist: tuple[str, ...] = ()
    suffix: str = ".py"

    def usage(self, sources: Mapping[str, bytes]) -> DefinitionUsage:
        scanner = Vulture(ignore_names=list(self.whitelist))
        for file, content in sources.items():
            scanner.scan(content.decode(errors="replace"), filename=file)
        _scan_bundled_whitelists(scanner)
        defined = (
            *scanner.defined_attrs,
            *scanner.defined_classes,
            *scanner.defined_funcs,
            *scanner.defined_imports,
            *scanner.defined_methods,
            *scanner.defined_props,
            *scanner.defined_vars,
        )
        return DefinitionUsage(
            defined=frozenset(_key(item) for item in defined),
            unused=tuple(
                UnusedDefinition(_key(item), item.first_lineno)
                for item in scanner.get_unused_code()
            ),
        )


def _scan_bundled_whitelists(scanner: Vulture) -> None:
    scanner.scavenge([])


def _key(item: Item) -> DefinitionKey:
    return DefinitionKey(str(item.filename), item.typ, item.name)
