from typing import Type
import io

def ftos(filename: str) -> str:
	reader: io.TextIOWrapper = open(filename, "r", encoding="utf-8")
	op: str = reader.read()
	reader.close()
	return op
