from enum import StrEnum


class ChangeKind(StrEnum):
    COMMENT = "comment"
    DOCSTRING = "docstring"
    IMPORT = "import"
    FUNCTION_SIGNATURE = "function-signature"
    FUNCTION_BODY = "function-body"
    TEST_FUNCTION = "test-function"
    FIXTURE = "fixture"
    HELPER_FUNCTION = "helper-function"
    CLASS_HEADER = "class-header"
    CLASS_ATTRIBUTE = "class-attribute"
    MODULE_STATEMENT = "module-statement"
    ANNOTATION = "annotation"
    CALL = "call"
    CONTROL_FLOW = "control-flow"
    RETURN_YIELD = "return-yield"
    COLLECTION_LITERAL = "collection-literal"
    STRING_LITERAL = "string-literal"
    NUMBER_LITERAL = "number-literal"
    ATTRIBUTE_ACCESS = "attribute-access"
    SUBSCRIPT = "subscript"
    CONDITIONAL_EXPRESSION = "conditional-expression"
    MEMBERSHIP_TEST = "membership-test"
    ASSERT = "assert"
    RAISE = "raise"
    DEFINITION_ADDED_OR_REMOVED = "definition-added-or-removed"
    CODE = "code"
    ANY = "any"

    @property
    def is_syntax_node(self) -> bool:
        return self not in _DERIVED


_DERIVED = frozenset({ChangeKind.DEFINITION_ADDED_OR_REMOVED, ChangeKind.CODE, ChangeKind.ANY})
