#!/usr/bin/env python3
"""Validate an output-only public edition. Generated copies are never edited."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from lxml import html

PAGES = ("index.html", "ebs-assessment-workflow.html",
         "incremental-models-2026.html", "where-things-live.html")
SITE = "https://afsc-assessments.github.io/pollock_prep_site/"
REPO = "afsc-assessments/pollock_prep_site"
FORBIDDEN = re.compile(
    r"/Users/|file://|herring_grid|tbl-top-shallow-vessels|observed-tracks\.csv|"
    r"inseas\d*\.csv|BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY|"
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", re.I)
ASSETS = {
    "site_libs/clipboard/clipboard.min.js",
    "site_libs/quarto-nav/quarto-nav.js",
    "site_libs/quarto-nav/headroom.min.js",
    "site_libs/quarto-search/autocomplete.umd.js",
    "site_libs/quarto-search/fuse.min.js",
    "site_libs/quarto-search/quarto-search.js",
    "site_libs/quarto-html/quarto.js",
    "site_libs/quarto-html/popper.min.js",
    "site_libs/quarto-html/tippy.umd.min.js",
    "site_libs/quarto-html/tippy.css",
    "site_libs/quarto-html/anchor.min.js",
    "site_libs/quarto-html/tabsets/tabsets.js",
    "site_libs/bootstrap/bootstrap.min.js",
    "site_libs/bootstrap/bootstrap-icons.css",
    "site_libs/bootstrap/bootstrap-icons.woff",
    "site_libs/quarto-contrib/glightbox/glightbox.min.js",
    "site_libs/quarto-contrib/glightbox/glightbox.min.css",
    "site_libs/quarto-contrib/glightbox/lightbox.css",
}
ASSET_HASH = re.compile(
    r"site_libs/(?:bootstrap/bootstrap-[a-f0-9]+\.min\.css|"
    r"quarto-html/quarto-syntax-highlighting-[a-f0-9]+\.css)")
ROOT_FILES = {"README.md", "LICENSE", "requirements.txt", "release.json",
              "inventory.json", ".github/workflows/pages.yml",
              "tools/public_release.py"}
DOC_FILES = set(PAGES) | {"search.json", "sitemap.xml", "robots.txt", "styles.css",
                          ".nojekyll", "provenance.json"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_text(text: str, path: str) -> None:
    if FORBIDDEN.search(text):
        raise ValueError(f"Excluded content or credential-shaped text in {path}")


def allowed_file(name: str) -> bool:
    if name in ROOT_FILES:
        return True
    if not name.startswith("docs/"):
        return False
    rel = name[5:]
    return rel in DOC_FILES or rel in ASSETS or bool(ASSET_HASH.fullmatch(rel))


def validate(root: Path, *, check_hashes: bool = True,
             allow_preview: bool = False) -> dict:
    root = root.resolve()
    files = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink is not publishable: {rel}")
        if not path.is_file():
            continue
        if not allowed_file(rel):
            raise ValueError(f"Unallowlisted public file: {rel}")
        files[rel] = path
        if path.suffix.lower() not in {".woff", ".woff2"} and rel != "tools/public_release.py":
            text = path.read_text(encoding="utf-8")
            if rel.startswith("docs/site_libs/"):
                # Reviewed Quarto runtime code tests the literal file protocol.
                # Keep all other payload/path/credential checks on these assets.
                text = text.replace("file://", "file-protocol:")
            check_text(text, rel)
    required = ROOT_FILES | {"docs/" + x for x in DOC_FILES}
    absent = required - set(files)
    if absent:
        raise ValueError(f"Missing public files: {sorted(absent)}")
    release = json.loads(files["release.json"].read_text())
    if release["public_repository"] != REPO or release["site_url"] != SITE:
        raise ValueError("Unexpected public destination")
    if not release["release_ready"] and not allow_preview:
        raise ValueError("Preview output cannot be published")
    if release["pages"] != list(PAGES) or len(set(release["pages"])) != len(PAGES):
        raise ValueError("Duplicate or unexpected public pages")
    if json.loads(files["docs/provenance.json"].read_text()) != release:
        raise ValueError("Public and repository provenance differ")
    inventory = json.loads(files["inventory.json"].read_text())
    if check_hashes:
        expected = inventory["files"]
        if set(expected) != set(files) - {"inventory.json"}:
            raise ValueError("Public inventory differs from actual file set")
        for name, recorded in expected.items():
            if digest(files[name]) != recorded["sha256"]:
                raise ValueError(f"Public file changed after validation: {name}")
    trees = {name: html.parse(str(files["docs/" + name])) for name in PAGES}
    titles = []
    link_count = 0
    for name, tree in trees.items():
        doc = tree.getroot()
        if not doc.get("lang", "").startswith("en"):
            raise ValueError(f"Missing document language: {name}")
        main = tree.xpath("//main")
        headings = tree.xpath("//main//h1")
        if len(main) != 1 or len(headings) != 1:
            raise ValueError(f"Missing or duplicate main title: {name}")
        titles.append(headings[0].text_content().strip())
        for table in tree.xpath("//main//table"):
            if not table.xpath(".//thead//th"):
                raise ValueError(f"Table has no column headers: {name}")
        # Main navigation contains each document exactly once.
        navigation = tree.xpath('//*[@id="quarto-sidebar"]//a[contains(@class,"sidebar-link")]/@href')
        normalized = []
        for value in navigation:
            part = urlsplit(value).path.rstrip("/").split("/")[-1] or "index.html"
            normalized.append(part)
        if sorted(normalized) != sorted(PAGES):
            raise ValueError(f"Duplicate or unexpected sidebar navigation: {name}")
        for element in tree.xpath("//*[@href] | //*[@src]"):
            value = element.get("href") or element.get("src")
            uri = urlsplit(value)
            if uri.scheme in {"mailto", "tel"}:
                raise ValueError(f"Unexpected contact action: {name}")
            if uri.scheme or uri.netloc:
                if uri.scheme != "https":
                    raise ValueError(f"Non-HTTPS external link: {name}")
                # Restricted destinations must identify access requirements in link text.
                if any(x in value for x in ["noaa-afsc/pollock_prep", "bookish-chainsaw-o8jopw4"]):
                    if "restricted" not in element.text_content().lower():
                        raise ValueError(f"Unlabeled restricted source link: {name}")
                continue
            part = unquote(uri.path)
            target = (files["docs/" + name].parent / part).resolve() if part else files["docs/" + name]
            if part.startswith("/"):
                prefix = "/pollock_prep_site/"
                if not part.startswith(prefix):
                    raise ValueError(f"Local link leaves public site: {value}")
                target = (root / "docs" / part[len(prefix):]).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.is_relative_to(root / "docs") or not target.is_file():
                raise ValueError(f"Broken or escaping local link in {name}: {value}")
            if uri.fragment and target.suffix == ".html":
                other = trees.get(target.name)
                if other is None or unquote(uri.fragment) not in other.xpath("//@id"):
                    raise ValueError(f"Broken fragment in {name}: {value}")
            link_count += 1
        canonical = tree.xpath('//link[@rel="canonical"]/@href')
        if canonical and canonical != [SITE + name]:
            raise ValueError(f"Wrong canonical public URL in {name}")
    if len(set(titles)) != len(PAGES):
        raise ValueError("Duplicate document titles")
    search = json.loads(files["docs/search.json"].read_text())
    search_hrefs = [x["href"] for x in search]
    search_pages = [urlsplit(x).path for x in search_hrefs]
    search_documents = [urlsplit(x).path for x in search_hrefs if not urlsplit(x).fragment]
    if (len(search_hrefs) != len(set(search_hrefs)) or set(search_pages) != set(PAGES)
            or sorted(search_documents) != sorted(PAGES)):
        raise ValueError("Search contains duplicate or unallowlisted documents/sections")
    sitemap = files["docs/sitemap.xml"].read_text()
    locations = re.findall(r"<loc>(.*?)</loc>", sitemap)
    if set(locations) != {SITE + x for x in PAGES} or len(locations) != len(PAGES):
        raise ValueError("Sitemap contains duplicate or unallowlisted pages")
    return {"status": "Pass", "pages": len(PAGES), "files": len(files),
            "local_links_checked": link_count, "inventory_hashes_checked": check_hashes,
            "duplicate_pages": 0, "excluded_payload_files": 0,
            "accessibility": "Language, main/title and table headers checked; screen-reader conformance not tested."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--allow-preview", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.release_dir, allow_preview=args.allow_preview), indent=2))


if __name__ == "__main__":
    main()
