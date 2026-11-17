#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import subprocess
import shutil
import time
import socket
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, List, Dict

# ──────────────────────────────────────────────
# Colors
# ──────────────────────────────────────────────
class C:
    R = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"

# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────
BANNER = f"""
{C.CYAN}{C.BOLD}
   ███████╗ ██████╗ ██████╗ ███████╗██████╗ 
   ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
   ███████╗██║   ██║██████╔╝█████╗  ██████╔╝
   ╚════██║██║   ██║██╔══██╗██╔══╝  ██╔══██╗
   ███████║╚██████╔╝██████╔╝███████╗██║  ██║
   ╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
{C.R}
{C.DIM}          Subdomain Enumeration Toolkit{C.R}
{C.YELLOW}                 v1.1  •  sober{C.R}
"""

# ──────────────────────────────────────────────
# Default tools & config
# ──────────────────────────────────────────────
DEFAULT_TOOLS = {
    "subfinder": "yes",
    "assetfinder": "yes",
    "findomain": "no",
    "amass": "yes",
    "chaos": "no",
    "crt.sh": "yes",
    "sublist3r": "yes",
    "ffuf": "no",
}

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "sober.conf"
WORDLIST = SCRIPT_DIR / "wordlist.txt"

# ──────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────
def load_config() -> Dict[str, str]:
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_TOOLS)
        return DEFAULT_TOOLS.copy()
    conf = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                conf[parts[0].lower()] = parts[1].lower()
    for t, v in DEFAULT_TOOLS.items():
        if t not in conf:
            conf[t] = v
    return conf

def save_config(conf: Dict[str, str]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("# sober config - yes/no\n")
        for tool in DEFAULT_TOOLS:
            val = conf.get(tool, DEFAULT_TOOLS[tool])
            f.write(f"{tool} {val}\n")

def set_tool(tool: str, value: str):
    tool = tool.lower()
    value = value.lower()
    if value not in ("yes", "no"):
        print(f"{C.RED}[!] value must be yes or no{C.R}")
        sys.exit(1)
    conf = load_config()
    if tool not in DEFAULT_TOOLS:
        print(f"{C.RED}[!] unknown tool: {tool}{C.R}")
        print(f"    available: {', '.join(DEFAULT_TOOLS.keys())}")
        sys.exit(1)
    conf[tool] = value
    save_config(conf)
    print(f"{C.GREEN}[+] {tool} → {value}{C.R}")

# ──────────────────────────────────────────────
# Tool runners
# ──────────────────────────────────────────────
def run_subfinder(domain: str) -> Set[str]:
    if not shutil.which("subfinder"):
        return set()
    try:
        p = subprocess.run(
            ["subfinder", "-d", domain, "-silent"],
            capture_output=True, text=True, timeout=300
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip()}
    except Exception:
        return set()

def run_assetfinder(domain: str) -> Set[str]:
    if not shutil.which("assetfinder"):
        return set()
    try:
        p = subprocess.run(
            ["assetfinder", "--subs-only", domain],
            capture_output=True, text=True, timeout=180
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip()}
    except Exception:
        return set()

def run_findomain(domain: str) -> Set[str]:
    if not shutil.which("findomain"):
        return set()
    try:
        p = subprocess.run(
            ["findomain", "-t", domain, "-q"],
            capture_output=True, text=True, timeout=180
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip()}
    except Exception:
        return set()

def run_amass(domain: str) -> Set[str]:
    if not shutil.which("amass"):
        return set()
    try:
        p = subprocess.run(
            ["amass", "enum", "-passive", "-d", domain, "-silent"],
            capture_output=True, text=True, timeout=400
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip()}
    except Exception:
        return set()

def run_chaos(domain: str) -> Set[str]:
    if not shutil.which("chaos"):
        return set()
    try:
        p = subprocess.run(
            ["chaos", "-d", domain, "-silent"],
            capture_output=True, text=True, timeout=180
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip()}
    except Exception:
        return set()

def run_crtsh(domain: str) -> Set[str]:
    try:
        import urllib.request
        import json
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        req = urllib.request.Request(url, headers={"User-Agent": "sober/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        results = set()
        for entry in data:
            name = entry.get("name_value", "")
            for line in name.split("\n"):
                line = line.strip().lower().lstrip("*.")
                if line.endswith("." + domain) or line == domain:
                    if line:
                        results.add(line)
        return results
    except Exception:
        return set()

def run_sublist3r(domain: str) -> Set[str]:
    if not shutil.which("sublist3r"):
        try:
            p = subprocess.run(
                ["python3", "-m", "sublist3r", "-d", domain, "-n"],
                capture_output=True, text=True, timeout=300
            )
            return {l.strip().lower() for l in p.stdout.splitlines() if l.strip() and domain in l}
        except Exception:
            return set()
    try:
        p = subprocess.run(
            ["sublist3r", "-d", domain, "-n"],
            capture_output=True, text=True, timeout=300
        )
        return {l.strip().lower() for l in p.stdout.splitlines() if l.strip() and domain in l}
    except Exception:
        return set()

def run_ffuf(domain: str) -> Set[str]:
    if not shutil.which("ffuf"):
        return set()
    if not WORDLIST.exists():
        print(f"{C.YELLOW}[!] wordlist.txt not found → skip ffuf{C.R}")
        return set()
    
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        subprocess.run(
            [
                "ffuf",
                "-u", f"https://FUZZ.{domain}",
                "-w", str(WORDLIST),
                "-mc", "200,201,202,204,301,302,307,401,403,405",
                "-t", "40",
                "-s",
                "-of", "csv",
                "-o", tmp_path,
            ],
            capture_output=True, text=True, timeout=600
        )
        results = set()
        with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("FUZZ") or not line:
                    continue
                parts = line.split(",")
                if parts:
                    sub = parts[0].strip().lower()
                    if sub:
                        results.add(f"{sub}.{domain}")
        return results
    except Exception:
        return set()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

# Internal TLD
COMMON_TLDS = [
    "com", "net", "org", "io", "co", "app", "dev", "me", "info", "biz",
    "xyz", "online", "site", "tech", "store", "shop", "cloud", "ai",
    "cc", "tv", "us", "uk", "de", "fr", "nl", "ru", "cn", "in", "br",
    "ca", "au", "jp", "kr", "sg", "hk", "tw", "id", "my", "ph", "vn",
]

def _resolve(host: str) -> bool:
    try:
        # Avoid global socket.setdefaulttimeout side-effect
        addr_info = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        if addr_info:
            return True
    except Exception:
        pass
    return False

def internal_tld_check(domain: str) -> Set[str]:
    if "." not in domain:
        return set()
    name = domain.rsplit(".", 1)[0]
    current_tld = domain.rsplit(".", 1)[1].lower()
    candidates = [f"{name}.{tld}" for tld in COMMON_TLDS if tld != current_tld]
    found = set()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_resolve, c): c for c in candidates}
        for fut in as_completed(futures):
            host = futures[fut]
            try:
                if fut.result():
                    found.add(host)
            except Exception:
                pass
    return found

# ──────────────────────────────────────────────
# Main engine
# ──────────────────────────────────────────────
TOOL_FUNCS = {
    "subfinder": run_subfinder,
    "assetfinder": run_assetfinder,
    "findomain": run_findomain,
    "amass": run_amass,
    "chaos": run_chaos,
    "crt.sh": run_crtsh,
    "sublist3r": run_sublist3r,
    "ffuf": run_ffuf,
}

def run_enumeration(domain: str):
    conf = load_config()
    enabled = [t for t, v in conf.items() if v == "yes" and t in TOOL_FUNCS]

    print(BANNER)
    print(f"{C.BOLD}Target:{C.R}  {C.CYAN}{domain}{C.R}")
    print(f"{C.BOLD}Tools:{C.R}   {C.GREEN}{len(enabled)} active{C.R} → {', '.join(enabled) or 'none'}")
    print(f"{C.DIM}{'─' * 55}{C.R}\n")

    if not enabled:
        print(f"{C.RED}[!] no tools enabled. use: python sober.py set <tool> yes{C.R}")
        return

    all_found: Set[str] = set()

    for i, tool in enumerate(enabled, 1):
        print(f"{C.BLUE}[{i}/{len(enabled)}]{C.R} running {C.BOLD}{tool}{C.R} ...", flush=True)
        start = time.time()
        try:
            results = TOOL_FUNCS[tool](domain)
        except Exception as e:
            print(f"    {C.RED}error: {e}{C.R}")
            results = set()

        elapsed = time.time() - start
        fresh = results - all_found
        all_found.update(results)

        if fresh:
            print(f"    {C.GREEN}+{len(fresh)} new{C.R}  ({len(results)} total from tool)  [{elapsed:.1f}s]")
            for sub in sorted(fresh):
                print(f"      {C.CYAN}{sub}{C.R}")
        else:
            print(f"    {C.DIM}0 new{C.R}  ({len(results)} total)  [{elapsed:.1f}s]")

    # Internal TLD
    print(f"\n{C.BLUE}[internal]{C.R} checking TLD variants ...", flush=True)
    tld_start = time.time()
    tld_found = internal_tld_check(domain)
    tld_elapsed = time.time() - tld_start

    if tld_found:
        print(f"    {C.GREEN}+{len(tld_found)} alive TLD variants{C.R}  [{tld_elapsed:.1f}s]")
        for v in sorted(tld_found):
            print(f"      {C.CYAN}{v}{C.R}")
            all_found.add(v)
    else:
        print(f"    {C.DIM}0 alive TLD variants{C.R}  [{tld_elapsed:.1f}s]")

    print(f"\n{C.DIM}{'─' * 55}{C.R}")
    print(f"{C.BOLD}Finished.{C.R}  Unique subdomains: {C.GREEN}{len(all_found)}{C.R}")
    if all_found:
        print()
        for s in sorted(all_found):
            print(s)

# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="sober",
        description="sober - subdomain enumeration toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python sober.py -d example.com
  python sober.py set ffuf yes
  python sober.py set amass no
  python sober.py --list
        """
    )
    parser.add_argument("-d", "--domain", help="target domain")
    parser.add_argument("command", nargs="?", help="set | list")
    parser.add_argument("tool", nargs="?", help="tool name for set")
    parser.add_argument("value", nargs="?", help="yes / no")
    parser.add_argument("--list", action="store_true", help="show current config")

    args = parser.parse_args()

    if args.command == "set":
        if not args.tool or not args.value:
            print(f"{C.RED}usage: python sober.py set <tool> <yes|no>{C.R}")
            sys.exit(1)
        set_tool(args.tool, args.value)
        return

    if args.command == "list" or args.list:
        conf = load_config()
        print(f"{C.BOLD}Current config ({CONFIG_FILE}):{C.R}\n")
        for t, v in conf.items():
            color = C.GREEN if v == "yes" else C.DIM
            print(f"  {t:<12} {color}{v}{C.R}")
        return

    if args.domain:
        domain = args.domain.lower().strip().rstrip(".")
        if domain.startswith("http"):
            domain = domain.split("//")[-1].split("/")[0]
        run_enumeration(domain)
        return

    print(BANNER)
    parser.print_help()

if __name__ == "__main__":
    main()
