#!/bin/zsh
cd -- "$(dirname -- "$0")/.." || exit 1
python3 scripts/serve_rpg.py
result=$?
if (( result != 0 )); then
  printf '\n실행 안내를 확인한 후 Enter를 누르세요.\n'
  read -r
fi
exit "$result"
