#!/usr/bin/env bash
# Run the README quick start against a fresh install in a temporary directory.
#
# Usage: scripts/e2e_quickstart.sh [path/to/llms_txt_gen-*.whl]
# Without an argument the wheel is built first. The sitemap step is served from
# 127.0.0.1 with python -m http.server, so no outside network is used.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
python="${PYTHON:-python3}"
wheel="${1:-}"
if [ -z "$wheel" ]; then
  rm -rf "$repo/dist"
  "$python" -m build --wheel --outdir "$repo/dist" "$repo" >/dev/null
  wheel="$(ls "$repo"/dist/llms_txt_gen-*.whl)"
fi
wheel="$(cd "$(dirname "$wheel")" && pwd)/$(basename "$wheel")"

work="$(mktemp -d)"
server_pid=""
cleanup() {
  if [ -n "$server_pid" ]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

"$python" -m venv "$work/venv"
"$work/venv/bin/pip" install --quiet --disable-pip-version-check "$wheel"
ltg="$work/venv/bin/llms-txt-gen"
cd "$work"
cp -R "$repo/examples/docs" docs

step() { printf '\n$ %s\n' "$*"; }

step llms-txt-gen generate docs/ --out llms.txt --base-url https://docs.example.com
"$ltg" generate docs/ --out llms.txt --base-url https://docs.example.com
grep -q '^# Acme Widgets$' llms.txt
grep -q '(https://docs.example.com/guides/quickstart.md)' llms.txt

step llms-txt-gen check llms.txt
"$ltg" check llms.txt

step llms-txt-gen serve-snippet
"$ltg" serve-snippet | grep -q 'rel="alternate" type="text/markdown" href="/llms.txt"'

# The sitemap step, served locally.
mkdir site
cp docs/guides/quickstart.md site/quickstart.md
printf '<html><head><title>API | Acme</title><meta name="description" content="Every endpoint."></head><body><h1>HTTP API</h1></body></html>\n' > site/api.html
port="$("$python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
cat > site/sitemap.xml <<XML
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://127.0.0.1:$port/quickstart.md</loc></url>
  <url><loc>http://127.0.0.1:$port/api.html</loc></url>
</urlset>
XML
"$python" -m http.server "$port" --bind 127.0.0.1 --directory site >/dev/null 2>&1 &
server_pid=$!
for _ in $(seq 50); do
  "$python" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$port/sitemap.xml', timeout=1)" 2>/dev/null && break
  sleep 0.1
done

step llms-txt-gen generate "http://127.0.0.1:$port/sitemap.xml" --out llms.txt --full
"$ltg" generate "http://127.0.0.1:$port/sitemap.xml" --out llms.txt --full
grep -q '\[HTTP API\](http://127.0.0.1:'"$port"'/api.html): Every endpoint.' llms.txt
grep -q '^Source: http://127.0.0.1:'"$port"'/quickstart.md$' llms-full.txt
"$ltg" check llms.txt

printf '\nquick start OK (%s)\n' "$("$ltg" --version)"
