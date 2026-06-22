#!/bin/bash
# Scan Alembic migration upgrade() functions for destructive operations.
# downgrade() functions are intentionally excluded — they are expected to be destructive.
# Exits non-zero when destructive ops are found unless FORCE_DESTRUCTIVE=true.
# Intended for CI pre-migrate gate and local pre-deploy review.
set -euo pipefail

MIGRATIONS_DIR="${1:-backend/app/db/migrations/versions}"
FORCE="${FORCE_DESTRUCTIVE:-false}"
FOUND=0

# Migrations listed here have been reviewed and approved — CI skips them.
EXCEPTIONS_FILE="${BASH_SOURCE%/*}/migration-exceptions.txt"

[ -d "${MIGRATIONS_DIR}" ] || { echo "ERROR: migrations dir not found: ${MIGRATIONS_DIR}"; exit 1; }

echo "Scanning upgrade() functions in: ${MIGRATIONS_DIR}"

# Python script that parses each migration file and inspects only the upgrade() body
CHECKER=$(cat <<'PYEOF'
import ast
import re
import sys
from pathlib import Path

PATTERNS = [
    r'op\.drop_table\b',
    r'op\.drop_column\b',
    r'op\.execute\s*\(.*(?:TRUNCATE|DROP\s|DELETE\s+FROM)',
    r'sa\.text\s*\(.*(?:TRUNCATE|DROP\s)',
]

path = Path(sys.argv[1])
content = path.read_text()

try:
    tree = ast.parse(content)
except SyntaxError as e:
    print(f"  SYNTAX ERROR: {e}", file=sys.stderr)
    sys.exit(0)

lines = content.splitlines()
hits = []

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'upgrade':
        for lineno in range(node.lineno, (node.end_lineno or node.lineno) + 1):
            line = lines[lineno - 1]
            for pattern in PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    hits.append(f"  {lineno}: {line.strip()}")
                    break

for h in hits:
    print(h)
PYEOF
)

is_excepted() {
    local filename
    filename=$(basename "$1")
    [ -f "${EXCEPTIONS_FILE}" ] || return 1
    grep -qxF "${filename}" "${EXCEPTIONS_FILE}" 2>/dev/null
}

while IFS= read -r -d '' file; do
    if is_excepted "${file}"; then
        continue
    fi
    output=$(python3 -c "${CHECKER}" "${file}" 2>/dev/null || true)
    if [ -n "${output}" ]; then
        echo "DESTRUCTIVE: ${file}"
        echo "${output}"
        FOUND=1
    fi
done < <(find "${MIGRATIONS_DIR}" -name "*.py" -print0 | sort -z)

if [ "${FOUND}" -eq 1 ]; then
    echo ""
    if [ "${FORCE}" = "true" ]; then
        echo "WARNING: Destructive upgrade() operations found. FORCE_DESTRUCTIVE=true — proceeding."
    else
        echo "ERROR: Destructive operations found in upgrade() functions."
        echo "Review each migration above before applying to production."
        echo "To bypass: FORCE_DESTRUCTIVE=true bash scripts/check-migrations.sh"
        exit 1
    fi
else
    echo "OK: No destructive operations in upgrade() functions."
fi
