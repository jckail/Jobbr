#!/usr/bin/env python3
"""Bounded, read-only Cloud Run/domain inventory; never emits secrets or tokens."""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request


def gcloud_json(*args, projection="json"):
    result = subprocess.run(
        ["gcloud", *args, f"--format={projection}", "--quiet"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        # CLI diagnostics can contain unexpectedly sensitive resource details.
        raise RuntimeError(f"gcloud {' '.join(args[:3])} failed (exit {result.returncode})")
    return json.loads(result.stdout)


def inventory(project, region):
    accounts = gcloud_json("auth", "list", "--filter=status:ACTIVE")
    if not accounts:
        raise RuntimeError("No active gcloud account; run gcloud auth login before preflight")
    report = {"project": project, "region": region, "active_account": accounts[0]["account"]}
    # Stable CLI lacks the regional list flag on some installations. Use GET on
    # the regional API instead of installing beta components or changing config.
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise RuntimeError("Could not acquire authenticated read-only API credential")
    token = result.stdout.strip()
    endpoint = (
        f"https://{region}-run.googleapis.com/apis/domains.cloudrun.com/v1/"
        f"namespaces/{project}/domainmappings"
    )
    request = urllib.request.Request(endpoint, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    mappings = []
    for item in data.get("items", []):
        domain = item.get("metadata", {}).get("name")
        if domain not in {"jckail.com", "www.jckail.com"}:
            continue
        mappings.append(
            {
                "domain": domain,
                "service": item.get("spec", {}).get("routeName"),
                "records": item.get("status", {}).get("resourceRecords", []),
                "conditions": [
                    {"type": c.get("type"), "status": c.get("status")}
                    for c in item.get("status", {}).get("conditions", [])
                ],
            }
        )
    report["domain_mappings"] = mappings
    report["mapped_services"] = []
    for service in sorted({m["service"] for m in mappings if m["service"]}):
        report["mapped_services"].append(
            gcloud_json(
                "run", "services", "describe", service,
                f"--project={project}", f"--region={region}",
                # Restrict server output; env vars never enter the report.
                projection="json(metadata.name,status.url,status.latestReadyRevisionName)",
            )
        )
    report["url_maps"] = gcloud_json(
        "compute", "url-maps", "list", f"--project={project}",
        projection="json(name,defaultService,hostRules,pathMatchers)",
    )
    report["forwarding_rules"] = gcloud_json(
        "compute", "forwarding-rules", "list", f"--project={project}",
        projection="json(name,IPAddress,IPProtocol,portRange,target)",
    )
    report["dns_zones"] = gcloud_json(
        "dns", "managed-zones", "list", f"--project={project}",
        projection="json(name,dnsName,visibility)",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Explicit inventory project; no CLI default")
    parser.add_argument("--region", required=True, help="Explicit region of existing domain mappings")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", args.project):
        parser.error("Expected a GCP project ID")
    if not re.fullmatch(r"[a-z]+-[a-z]+[0-9]", args.region):
        parser.error("Expected a GCP region")
    try:
        report = inventory(args.project, args.region)
        # Keep OS DNS blocking out of this process; each fixed host lookup is killable.
        report["dns"] = {}
        lookup = (
            "import json,socket,sys; "
            "print(json.dumps(sorted({v[4][0] for v in socket.getaddrinfo(sys.argv[1],443)})))"
        )
        for host in ("jckail.com", "www.jckail.com"):
            result = subprocess.run(
                [sys.executable, "-I", "-c", lookup, host],
                capture_output=True, text=True, timeout=5, check=True,
            )
            report["dns"][host] = json.loads(result.stdout)

        print(json.dumps(report, indent=2))
        return 0
    except urllib.error.HTTPError as exc:
        print(f"Read-only API inventory failed (HTTP {exc.code}); check IAM/API access", file=sys.stderr)
    except RuntimeError as exc:
        # These messages are authored above, never copied from provider bodies.
        print(f"Preflight failed: {exc}", file=sys.stderr)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, ValueError) as exc:
        # Never print request objects, provider bodies or captured credential output.
        print(f"Preflight failed: {type(exc).__name__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
