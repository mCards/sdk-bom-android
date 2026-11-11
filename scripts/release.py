#!/usr/bin/env python3
"""Stage an immutable customer Maven release; publish only with --publish.

SDK binaries and metadata are copied unchanged. Only the BoM coordinate changes
from bom-internal to bom. Maven handles upload checksums and repository metadata.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = "https://maven.pkg.github.com/mCards/sdk-bom-android"
NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def coordinate_path(item):
    return f"{item['group'].replace('.', '/')}/{item['name']}/{item['version']}"


def download(url, username, token, optional=False):
    auth = base64.b64encode(f"{username}:{token}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if optional and error.code == 404:
            return None
        raise RuntimeError(f"HTTP {error.code} fetching {url}") from None


def rewrite_bom(pom, module, version):
    # Replace only the publication's coordinates, never dependency versions.
    tree = ET.fromstring(pom)
    tree.find("m:artifactId", NS).text = "bom"
    tree.find("m:version", NS).text = version
    ET.register_namespace("", NS["m"])
    # Gradle's marker tells consumers to load the accompanying .module metadata.
    pom = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
    pom = pom.replace(b"<modelVersion>", b"<!-- do_not_remove: published-with-gradle-metadata -->\n  <modelVersion>", 1)
    metadata = json.loads(module)
    metadata["component"]["module"] = "bom"
    metadata["component"]["version"] = version
    return pom, (json.dumps(metadata, indent=2) + "\n").encode()


def validate_bom(pom, artifacts):
    tree = ET.fromstring(pom)
    actual = {d.findtext("m:artifactId", namespaces=NS): d.findtext("m:version", namespaces=NS)
              for d in tree.findall("m:dependencyManagement/m:dependencies/m:dependency", NS)}
    expected = {a["name"]: a["version"] for a in artifacts if a["group"] == "com.mcards.sdk"}
    if actual != expected:
        raise ValueError(f"Reference BoM does not match release.json: {actual} != {expected}")


def stage_item(item, output, username, token):
    directory = output / coordinate_path(item)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{item['name']}-{item['version']}"
    base = f"https://maven.pkg.github.com/{item['repository']}/{coordinate_path(item)}"
    pom = download(f"{base}/{stem}.pom", username, token)
    module = download(f"{base}/{stem}.module", username, token, optional=True)
    packaging = ET.fromstring(pom).findtext("m:packaging", default="jar", namespaces=NS)
    files = {f"{stem}.pom": pom}
    if module is not None:
        files[f"{stem}.module"] = module
        for variant in json.loads(module).get("variants", []):
            for entry in variant.get("files", []):
                name = entry["url"]
                if Path(name).name != name or not name.startswith(stem):
                    raise ValueError(f"Unexpected artifact path: {name}")
                data = download(f"{base}/{name}", username, token)
                for algorithm in ("sha512", "sha256", "sha1", "md5"):
                    if algorithm in entry and hashlib.new(algorithm, data).hexdigest() != entry[algorithm]:
                        raise ValueError(f"Checksum mismatch: {name} ({algorithm})")
                files[name] = data
    main = f"{stem}.{packaging}"
    if main not in files:
        files[main] = download(f"{base}/{main}", username, token)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return {**item, "packaging": packaging, "files": sorted(files)}


def check_lock(items, output, lock_path, write=False):
    hashes = {f"{coordinate_path(item)}/{name}": hashlib.sha256(
        (output / coordinate_path(item) / name).read_bytes()).hexdigest()
        for item in items for name in item["files"]}
    if write:
        lock_path.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    elif json.loads(lock_path.read_text()) != hashes:
        raise ValueError("Artifact content differs from release-lock.json; refusing to publish")


def already_published(item, output, username, token):
    # All files must match; a partial/different existing release requires maintainer investigation.
    results = []
    for name in item["files"]:
        remote = download(f"{DESTINATION}/{coordinate_path(item)}/{name}", username, token, optional=True)
        if remote is not None and remote != (output / coordinate_path(item) / name).read_bytes():
            raise ValueError(f"Existing customer artifact differs: {name}")
        results.append(remote is not None)
    if any(results) and not all(results):
        raise ValueError(f"Partial customer release exists: {item['name']} {item['version']}")
    return all(results)


def publish(item, output, settings):
    directory = output / coordinate_path(item)
    stem = f"{item['name']}-{item['version']}"
    main = f"{stem}.{item['packaging']}"
    attachments = [name for name in item["files"] if name not in (main, f"{stem}.pom")]
    command = ["mvn", "--batch-mode", "--no-transfer-progress", "--settings", str(settings),
               "org.apache.maven.plugins:maven-deploy-plugin:3.1.4:deploy-file",
               "-DrepositoryId=customer", f"-Durl={DESTINATION}",
               f"-Dfile={directory / main}", f"-DpomFile={directory / (stem + '.pom')}", "-DretryFailedDeploymentCount=3"]
    if attachments:
        command += ["-Dfiles=" + ",".join(str(directory / name) for name in attachments),
                    "-Dtypes=" + ",".join(Path(name).suffix[1:] for name in attachments),
                    "-Dclassifiers=" + ",".join(Path(name).stem[len(stem):].lstrip("-") for name in attachments)]
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "staged")
    parser.add_argument("--write-lock", action="store_true", help="Record reviewed source hashes; never publish")
    parser.add_argument("--publish", action="store_true", help="Upload after complete staging, checksum and destination checks")
    args = parser.parse_args()
    if args.write_lock and args.publish:
        parser.error("--write-lock cannot be combined with --publish")
    username = os.environ["GH_PACKAGES_USER"]
    source_token = os.environ["GH_PACKAGES_READ_TOKEN"]
    config = json.loads((ROOT / "release.json").read_text())
    output = args.output.resolve()
    items = []
    for item in config["artifacts"]:
        print(f"Staging {item['name']} {item['version']}", flush=True)
        items.append(stage_item(item, output, username, source_token))
    reference = {"group": "com.mcards.sdk", "name": "bom-internal", **config["referenceBom"]}
    base = f"https://maven.pkg.github.com/{reference['repository']}/{coordinate_path(reference)}/bom-internal-{reference['version']}"
    pom = download(base + ".pom", username, source_token)
    module = download(base + ".module", username, source_token)
    validate_bom(pom, config["artifacts"])
    pom, module = rewrite_bom(pom, module, config["version"])
    bom = {"group": "com.mcards.sdk", "name": "bom", "version": config["version"], "packaging": "pom",
           "files": [f"bom-{config['version']}.pom", f"bom-{config['version']}.module"]}
    directory = output / coordinate_path(bom)
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in zip(bom["files"], (pom, module)):
        (directory / name).write_bytes(data)
    items.append(bom)  # Publish the BoM only after every dependency is available.
    check_lock(items, output, ROOT / "release-lock.json", args.write_lock)
    (output / "release-plan.json").write_text(json.dumps(items, indent=2) + "\n")
    if not args.publish:
        print("Staged and verified; nothing published.")
        return
    destination_token = os.environ["GH_PACKAGES_WRITE_TOKEN"]
    pending = [item for item in items if not already_published(item, output, username, destination_token)]
    with tempfile.TemporaryDirectory() as temp:
        settings = Path(temp) / "settings.xml"
        settings.write_text('''<settings><servers><server><id>customer</id>
<username>${env.GH_PACKAGES_USER}</username><password>${env.GH_PACKAGES_WRITE_TOKEN}</password>
</server></servers></settings>''')
        settings.chmod(0o600)
        for item in pending:
            publish(item, output, settings)
            if not already_published(item, output, username, destination_token):
                raise RuntimeError(f"Upload verification failed: {item['name']}")


if __name__ == "__main__":
    main()
