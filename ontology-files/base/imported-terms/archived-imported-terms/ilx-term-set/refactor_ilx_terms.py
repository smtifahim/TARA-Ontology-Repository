"""
refactor_ilx_terms.py

Refactors tara-ilx-terms.ttl by:
  1. For every FMA:XXXX a owl:Class block, replacing the subject IRI
     (FMA:XXXX) with the ILX: identifier found via ilxtr:hasIlxId.
  2. Removing the three metadata triples:
       ilxtr:hasExternalId FMA:XXXX ;
       ilxtr:hasIlxId ILX:XXXXXXX ;
       ilxtr:hasIlxPreferredId FMA:XXXX ;
  3. Replacing any rdfs:subClassOf FMA:XXXX with the corresponding ILX id
     using the mapping built from step 1.

Output is written to tara-ilx-terms-refactored.ttl in the same directory.
"""

import re
from pathlib import Path

INPUT_FILE = Path(__file__).parent / "tara-ilx-terms.ttl"
OUTPUT_FILE = Path(__file__).parent / "tara-ilx-terms-refactored.ttl"


def split_blocks(text: str) -> "list[str]":
    """Split the file into parts separated by blank lines, keeping separators."""
    return re.split(r'(\n{2,})', text)


def build_fma_to_ilx_map(parts: "list[str]") -> "dict[str, str]":
    """
    Scan all blocks and return a dict mapping FMA:XXXX -> ILX:XXXXXXX
    based on ilxtr:hasIlxId triples in FMA owl:Class blocks.
    """
    mapping = {}
    for block in parts:
        fma_match = re.match(r'\s*(FMA:\w+)\s+a\s+owl:Class', block)
        if not fma_match:
            continue
        ilx_match = re.search(r'ilxtr:hasIlxId\s+(ILX:\d+)\s*;', block)
        if ilx_match:
            mapping[fma_match.group(1)] = ilx_match.group(1)
    return mapping


def refactor_fma_block(block: str, fma_to_ilx: "dict[str, str]") -> str:
    """
    Given a Turtle block for an FMA:XXXX owl:Class, return the refactored block.
    Returns the block unchanged if it is not an FMA owl:Class block.
    """
    # Only process blocks that start with FMA: and declare owl:Class
    fma_match = re.match(r'\s*(FMA:\w+)\s+a\s+owl:Class', block)
    if not fma_match:
        return block

    fma_id = fma_match.group(1)
    ilx_id = fma_to_ilx.get(fma_id)
    if not ilx_id:
        # No ILX id found – leave block unchanged
        return block

    # 1. Replace the subject IRI FMA:XXXX with ILX:XXXXXXX
    block = re.sub(
        r'^(\s*)' + re.escape(fma_id) + r'(\s+a\s+owl:Class)',
        r'\g<1>' + ilx_id + r'\2',
        block,
        count=1,
        flags=re.MULTILINE,
    )

    # 2. Remove ilxtr:hasExternalId line (the whole line including trailing newline)
    block = re.sub(
        r'[ \t]*ilxtr:hasExternalId\s+' + re.escape(fma_id) + r'\s*;\n',
        '',
        block,
    )

    # 3. Remove ilxtr:hasIlxId line
    block = re.sub(
        r'[ \t]*ilxtr:hasIlxId\s+' + re.escape(ilx_id) + r'\s*;\n',
        '',
        block,
    )

    # 4. Remove ilxtr:hasIlxPreferredId line
    block = re.sub(
        r'[ \t]*ilxtr:hasIlxPreferredId\s+' + re.escape(fma_id) + r'\s*;\n',
        '',
        block,
    )

    return block


def replace_subclassof_fma(text: str, fma_to_ilx: "dict[str, str]") -> str:
    """
    Replace every  rdfs:subClassOf FMA:XXXX  reference in the full text
    with the corresponding ILX id from the mapping.
    """
    def _replacer(m: re.Match) -> str:
        fma_id = m.group(1)
        ilx_id = fma_to_ilx.get(fma_id)
        if ilx_id:
            return m.group(0).replace(fma_id, ilx_id)
        return m.group(0)  # no mapping found – leave unchanged

    return re.sub(r'rdfs:subClassOf\s+(FMA:\w+)', _replacer, text)


def main():
    text = INPUT_FILE.read_text(encoding="utf-8")

    # Split on blank-line boundaries while keeping separators so we can rejoin
    parts = re.split(r'(\n{2,})', text)

    # Build FMA -> ILX mapping from all FMA owl:Class blocks before transforming
    fma_to_ilx = build_fma_to_ilx_map(parts)

    # Refactor each FMA block (rename subject, remove metadata triples)
    refactored_parts = [refactor_fma_block(part, fma_to_ilx) for part in parts]

    # Rejoin and then replace any rdfs:subClassOf FMA: references globally
    result = "".join(refactored_parts)
    result = replace_subclassof_fma(result, fma_to_ilx)

    # Replace ns1: prefix with oboInOwl: throughout
    result = result.replace("ns1:", "oboInOwl:")

    # Remove the @prefix ns1: line
    result = re.sub(r'@prefix ns1:.*\n', '', result)

    OUTPUT_FILE.write_text(result, encoding="utf-8")
    print(f"Refactored file written to: {OUTPUT_FILE}")
    print(f"FMA -> ILX mappings applied: {len(fma_to_ilx)}")


if __name__ == "__main__":
    main()
