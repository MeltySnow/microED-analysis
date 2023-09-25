from typing import Type

def ftos(filename: str) -> str:
	reader: _io.TextIOWrapper = open(filename, "r", encoding="utf-8")
	op: str = reader.read()
	reader.close()
	return op
