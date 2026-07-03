#!/bin/bash
# Compile staged Python files passed by Lefthook.

if [ $# -eq 0 ]; then
  exit 0
fi

python_files=()
for file in "$@"; do
  if [[ "$file" == *.py && -f "$file" ]]; then
    python_files+=("$file")
  fi
done

if [ ${#python_files[@]} -eq 0 ]; then
  exit 0
fi

cache_dir="$(mktemp -d)"
trap 'rm -rf "$cache_dir"' EXIT

PYTHONPYCACHEPREFIX="$cache_dir" python3 -m py_compile "${python_files[@]}"
