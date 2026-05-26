from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

from .model import Operation, SourceSpan

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CALL = re.compile(
    r"^\s*(?P<name>network(?:\.[A-Za-z_][A-Za-z0-9_]*){2,})\s*"
    r"\((?P<args>.*)\)\s*$",
    re.DOTALL,
)
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


class ParseError(ValueError):
    def __init__(
        self,
        message: str,
        path: str | None = None,
        line: int = 1,
        column: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.line = line
        self.column = column

    def __str__(self) -> str:
        location = SourceSpan(self.path, self.line, self.column).label()
        return f"{location}: {self.message}"


def parse_file(path: str | Path) -> list[Operation]:
    source = Path(path)
    return parse_text(source.read_text(encoding="utf-8"), path=str(source))


def parse_text(text: str, path: str | None = None) -> list[Operation]:
    operations = []
    for statement, line in _statements(text, path):
        operations.append(_parse_operation(statement, path, line))
    return operations


def _parse_operation(statement: str, path: str | None, line: int) -> Operation:
    match = _CALL.match(statement)
    if not match:
        raise ParseError("expected operation call like network.path.action(...)", path, line)

    parts = match.group("name").split(".")
    namespace = parts[0]
    resource_path = tuple(parts[1:-1])
    action = parts[-1]
    params = _ValueParser(match.group("args"), path, line).parse_arguments()

    return Operation(
        namespace=namespace,
        resource_path=resource_path,
        action=action,
        params=params,
        source=SourceSpan(path, line, 1),
    )


def _statements(text: str, path: str | None) -> Iterable[tuple[str, int]]:
    buffer: list[str] = []
    start_line = 1
    depth = 0

    for line_number, original_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(original_line).rstrip()
        if not line.strip() and not buffer:
            continue

        if not buffer:
            start_line = line_number

        buffer.append(line)
        depth += _depth_delta(line, path, line_number)

        if depth < 0:
            raise ParseError("unexpected closing delimiter", path, line_number)

        if buffer and depth == 0:
            statement = "\n".join(buffer).strip()
            if statement:
                yield statement, start_line
            buffer = []

    if buffer:
        raise ParseError("unclosed operation call", path, start_line)


def _strip_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote:
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None:
            return line[:index]
    return line


def _depth_delta(line: str, path: str | None, line_number: int) -> int:
    quote: str | None = None
    escaped = False
    delta = 0

    for column, char in enumerate(line, start=1):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote:
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if quote:
            continue
        if char in "([{":
            delta += 1
        elif char in ")]}":
            delta -= 1
            if delta < -1:
                raise ParseError("unexpected closing delimiter", path, line_number, column)

    if quote:
        raise ParseError("unterminated string literal", path, line_number)
    return delta


class _ValueParser:
    def __init__(self, text: str, path: str | None, start_line: int) -> None:
        self.text = text
        self.path = path
        self.start_line = start_line
        self.index = 0

    def parse_arguments(self) -> dict[str, Any]:
        args: dict[str, Any] = {}
        self._skip_ws()
        if self._done():
            return args

        while True:
            key = self._identifier("expected argument name")
            self._skip_ws()
            self._expect("=")
            value = self._value()
            if key in args:
                self._error(f"duplicate argument '{key}'")
            args[key] = value

            self._skip_ws()
            if self._done():
                return args
            self._expect(",")
            self._skip_ws()
            if self._done():
                return args

    def _value(self) -> Any:
        self._skip_ws()
        if self._done():
            self._error("expected value")

        char = self.text[self.index]
        if char in {"'", '"'}:
            return self._string()
        if char == "{":
            return self._object()
        if char == "[":
            return self._list()
        if char == "-" or char.isdigit():
            return self._number()

        word = self._identifier("expected value")
        if word == "true":
            return True
        if word == "false":
            return False
        if word == "null":
            return None
        self._error(f"unknown literal '{word}'")

    def _object(self) -> dict[str, Any]:
        self._expect("{")
        result: dict[str, Any] = {}
        self._skip_ws()
        if self._consume("}"):
            return result

        while True:
            key = self._identifier("expected object key")
            self._skip_ws()
            self._expect("=")
            result[key] = self._value()
            self._skip_ws()
            if self._consume("}"):
                return result
            self._expect(",")
            self._skip_ws()
            if self._consume("}"):
                return result

    def _list(self) -> list[Any]:
        self._expect("[")
        result: list[Any] = []
        self._skip_ws()
        if self._consume("]"):
            return result

        while True:
            result.append(self._value())
            self._skip_ws()
            if self._consume("]"):
                return result
            self._expect(",")
            self._skip_ws()
            if self._consume("]"):
                return result

    def _string(self) -> str:
        quote = self.text[self.index]
        start = self.index
        self.index += 1
        escaped = False

        while not self._done():
            char = self.text[self.index]
            self.index += 1
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                return ast.literal_eval(self.text[start : self.index])

        self._error("unterminated string literal")

    def _number(self) -> int | float:
        match = _NUMBER.match(self.text, self.index)
        if not match:
            self._error("expected number")
        raw = match.group(0)
        self.index = match.end()
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)

    def _identifier(self, message: str) -> str:
        self._skip_ws()
        match = _IDENTIFIER.match(self.text, self.index)
        if not match:
            self._error(message)
        self.index = match.end()
        return match.group(0)

    def _expect(self, expected: str) -> None:
        self._skip_ws()
        if not self.text.startswith(expected, self.index):
            self._error(f"expected '{expected}'")
        self.index += len(expected)

    def _consume(self, expected: str) -> bool:
        self._skip_ws()
        if self.text.startswith(expected, self.index):
            self.index += len(expected)
            return True
        return False

    def _skip_ws(self) -> None:
        while not self._done() and self.text[self.index].isspace():
            self.index += 1

    def _done(self) -> bool:
        return self.index >= len(self.text)

    def _error(self, message: str) -> None:
        line = self.start_line + self.text.count("\n", 0, self.index)
        last_newline = self.text.rfind("\n", 0, self.index)
        column = self.index + 1 if last_newline == -1 else self.index - last_newline
        raise ParseError(message, self.path, line, column)

