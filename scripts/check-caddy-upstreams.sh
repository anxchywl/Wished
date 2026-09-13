#!/usr/bin/env bash
# Verify every reverse_proxy upstream in the production Caddyfile resolves to
# exactly one container.
#
# This host runs several compose projects behind one Caddy, sharing the
# wished_wished-app network. Compose always registers a service's own name as a
# network alias and gives no way to suppress it, so two projects that each name
# a service `backend` make `backend` ambiguous on that network: Docker's
# embedded DNS round-robins across both and requests land on whichever app
# answers. Nothing errors — the wrong app just returns 404 for routes it has
# never heard of — so the failure is invisible until users report it. That is
# what happened on 2026-09-12, when ~2 of every 3 Wished API calls were served
# by Muto or Gradus. Check it at deploy time instead.
set -euo pipefail

CADDYFILE="${CADDYFILE:-infra/caddy/Caddyfile.production}"
CADDY_CONTAINER="${CADDY_CONTAINER:-wished-caddy}"

[ -f "${CADDYFILE}" ] || { echo "ERROR: Caddyfile not found: ${CADDYFILE}" >&2; exit 1; }

if ! docker ps --format '{{.Names}}' | grep -qx "${CADDY_CONTAINER}"; then
    echo "SKIP: ${CADDY_CONTAINER} is not running; cannot resolve upstreams." >&2
    exit 0
fi

# `reverse_proxy host:port` -> host, deduplicated. Upstreams with a scheme or a
# placeholder are skipped: they are not bare DNS names.
mapfile -t upstreams < <(
    grep -oE '^[[:space:]]*reverse_proxy[[:space:]]+[A-Za-z0-9_.-]+:[0-9]+' "${CADDYFILE}" \
        | awk '{print $2}' | cut -d: -f1 | sort -u
)

[ "${#upstreams[@]}" -gt 0 ] || { echo "ERROR: no upstreams found in ${CADDYFILE}" >&2; exit 1; }

failed=0
for host in "${upstreams[@]}"; do
    # one "Name:/Address:" pair per answer; the leading server line is excluded
    # because it is not preceded by a Name: line
    count=$(docker exec "${CADDY_CONTAINER}" nslookup "${host}" 2>/dev/null \
        | grep -A1 '^Name:' | grep -c '^Address' || true)

    case "${count}" in
        1) printf '  %-24s 1 container    OK\n' "${host}" ;;
        0) printf '  %-24s UNRESOLVABLE   FAIL\n' "${host}"; failed=1 ;;
        *) printf '  %-24s %s containers   FAIL (ambiguous)\n' "${host}" "${count}"; failed=1 ;;
    esac
done

if [ "${failed}" -ne 0 ]; then
    cat >&2 <<'MSG'

ERROR: at least one Caddy upstream does not resolve to exactly one container.

An ambiguous name means another compose project on the shared network exposes
that same name, and Docker will round-robin between them. Point the site block
at a name unique to this project (its container_name), or rename the colliding
service in the other project.
MSG
    exit 1
fi

echo "All ${#upstreams[@]} Caddy upstreams resolve to exactly one container."
