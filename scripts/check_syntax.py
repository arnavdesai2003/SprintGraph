"""Optional offline TypeScript/TSX syntax check, not a substitute for tsc."""
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_typescript as ts
root = Path(__file__).resolve().parents[1]
count = 0
for path in (root / 'frontend').rglob('*'):
    if path.suffix not in {'.ts', '.tsx'} or 'node_modules' in path.parts or '.next' in path.parts:
        continue
    parser = Parser(Language(ts.language_tsx() if path.suffix == '.tsx' else ts.language_typescript()))
    tree = parser.parse(path.read_bytes())
    if tree.root_node.has_error:
        raise SystemExit(f'Syntax error: {path.relative_to(root)}')
    count += 1
print(f'PASS: parsed {count} TypeScript/TSX files; semantic typecheck still requires npm dependencies')
