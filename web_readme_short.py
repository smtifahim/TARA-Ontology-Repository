import pathlib
content = "Test content"
p = pathlib.Path("ontology-files/readme.md")
p.write_text(content, encoding="utf-8")
print("Written test")
