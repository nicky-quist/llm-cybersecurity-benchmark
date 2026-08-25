"""
MITRE ATT&CK technique context lookup.

Covers the technique set produced by soc-triage-tool's offline analysis engine
(see soc-triage-tool/src/SOCTriageTool.jsx) so alerts coming out of that tool
can be enriched with tactic-level context before being handed to an LLM for
a recommendation. Static and offline by design — no network dependency for
this lookup, matching soc-triage-tool's own "deterministic, offline" ethos.

Descriptions are original short summaries, not reproductions of MITRE's text.
"""

ATTACK_TECHNIQUES = {
    "T1110": {
        "name": "Brute Force",
        "tactic": "Credential Access",
        "summary": "Repeated, systematic login attempts against one or more accounts to guess valid credentials.",
        "typical_mitigations": [
            "Account lockout / rate limiting after N failed attempts",
            "Enforce MFA on all externally reachable auth endpoints",
            "Alert on failed-login velocity per source IP and per account",
        ],
    },
    "T1110.001": {
        "name": "Brute Force: Password Guessing",
        "tactic": "Credential Access",
        "summary": "Automated password guessing against a known or common username, often targeting privileged accounts like root/admin.",
        "typical_mitigations": [
            "Disable password-only SSH auth in favor of key-based auth",
            "fail2ban / IPS rules to auto-block after threshold",
            "Rotate credentials for any targeted account regardless of apparent success",
        ],
    },
    "T1059.001": {
        "name": "Command and Scripting Interpreter: PowerShell",
        "tactic": "Execution",
        "summary": "Use of PowerShell — often with encoding, download cradles, or hidden windows — to execute attacker code or stage a second payload.",
        "typical_mitigations": [
            "Enable PowerShell Script Block Logging (Event ID 4104) fleet-wide",
            "Constrained Language Mode / AppLocker for non-admin users",
            "Alert on EncodedCommand, IEX, DownloadString, and -WindowStyle Hidden combinations",
        ],
    },
    "T1548.003": {
        "name": "Abuse Elevation Control Mechanism: Sudo and Sudo Caching",
        "tactic": "Privilege Escalation",
        "summary": "Use of sudo/su to elevate privileges, legitimate in most cases but worth confirming against an authorized-admin baseline.",
        "typical_mitigations": [
            "Review /etc/sudoers regularly against an approved list",
            "Log and alert on sudo usage outside of change windows",
        ],
    },
    "T1547.001": {
        "name": "Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder",
        "tactic": "Persistence",
        "summary": "Writing to autostart registry keys, the Startup folder, or scheduled tasks so malicious code survives reboot.",
        "typical_mitigations": [
            "Baseline and diff Run/RunOnce keys and scheduled tasks",
            "Restrict write access to autostart locations for standard users",
        ],
    },
    "T1021": {
        "name": "Remote Services",
        "tactic": "Lateral Movement",
        "summary": "Use of legitimate remote access (SMB shares, PsExec, RDP, WMI) to move between hosts, often indistinguishable from normal admin activity without context.",
        "typical_mitigations": [
            "Restrict admin-share and PsExec usage to a documented jump-host workflow",
            "Alert on remote-service usage from non-admin source hosts",
        ],
    },
    "T1071": {
        "name": "Application Layer Protocol",
        "tactic": "Command and Control",
        "summary": "C2 traffic disguised as normal application-layer protocol traffic (HTTP/HTTPS/DNS) to blend into legitimate network flows.",
        "typical_mitigations": [
            "TLS inspection / JA3 fingerprinting on egress",
            "Egress allow-listing for servers that shouldn't reach arbitrary internet hosts",
        ],
    },
    "T1071.001": {
        "name": "Application Layer Protocol: Web Protocols",
        "tactic": "Command and Control",
        "summary": "C2 over HTTP/HTTPS, frequently used by frameworks like Cobalt Strike to blend with normal web traffic.",
        "typical_mitigations": [
            "Block known C2 infrastructure via threat intel feeds",
            "Inspect for JA3/JA3S and beaconing interval patterns",
        ],
    },
    "T1071.004": {
        "name": "Application Layer Protocol: DNS",
        "tactic": "Command and Control",
        "summary": "Using the DNS protocol itself as a C2 or tunneling channel, often via unusually long or high-entropy subdomains.",
        "typical_mitigations": [
            "DNS query length/entropy monitoring",
            "Restrict recursive DNS to approved resolvers only",
        ],
    },
    "T1048": {
        "name": "Exfiltration Over Alternative Protocol",
        "tactic": "Exfiltration",
        "summary": "Moving data out over a channel other than the primary C2 channel — large or unusual outbound transfers are the key signal.",
        "typical_mitigations": [
            "DLP on egress for sensitive data patterns",
            "Alert on large outbound transfers from hosts that shouldn't generate them",
        ],
    },
    "T1048.003": {
        "name": "Exfiltration Over Alternative Protocol: DNS",
        "tactic": "Exfiltration",
        "summary": "Encoding stolen data into DNS query labels (often Base64) to exfiltrate past controls that don't inspect DNS payloads.",
        "typical_mitigations": [
            "Sinkhole suspect domains at the resolver",
            "Alert on high-entropy or Base64-pattern subdomains",
        ],
    },
    "T1571": {
        "name": "Non-Standard Port",
        "tactic": "Command and Control",
        "summary": "C2 or data transfer over a port that doesn't match the protocol's expected default, a common evasion of naive port-based filtering.",
        "typical_mitigations": [
            "Protocol-aware inspection rather than port-based filtering alone",
            "Alert on known malware-associated ports (4444, 1337, 31337, etc.)",
        ],
    },
    "T1190": {
        "name": "Exploit Public-Facing Application",
        "tactic": "Initial Access",
        "summary": "Exploiting a vulnerability in an internet-reachable service to gain a foothold.",
        "typical_mitigations": [
            "Timely patching of internet-facing services (WAF as compensating control only)",
            "Verify exploited service's patch level immediately after any exploit-signature alert",
        ],
    },
    "T1595": {
        "name": "Active Scanning",
        "tactic": "Reconnaissance",
        "summary": "Scanning or probing to discover live hosts, open ports, or service versions ahead of a later attack stage.",
        "typical_mitigations": [
            "Block or rate-limit scan sources at the perimeter",
            "Treat repeated scanning from the same source as an early-warning signal, not noise",
        ],
    },
    "T1003": {
        "name": "OS Credential Dumping",
        "tactic": "Credential Access",
        "summary": "Extracting credentials from OS memory or storage (e.g., LSASS via Mimikatz), giving an attacker material for lateral movement even if the initial action was blocked.",
        "typical_mitigations": [
            "Credential Guard / LSA protection",
            "Treat any dumping-tool detection as a compromise regardless of block status; force credential rotation",
        ],
    },
    "T1082": {
        "name": "System Information Discovery",
        "tactic": "Discovery",
        "summary": "Commands like whoami, net user, or systeminfo used by an attacker (or legitimate admin) to orient within a compromised environment.",
        "typical_mitigations": [
            "Correlate discovery commands with the account's normal behavior baseline",
            "Low signal alone; treat as a strong signal only when paired with other indicators",
        ],
    },
    "T1566": {
        "name": "Phishing",
        "tactic": "Initial Access",
        "summary": "Delivery of malicious content (links or payloads) via email or messaging to gain initial access or credentials.",
        "typical_mitigations": [
            "Email attachment/link sandboxing",
            "User reporting workflow tied to a fast SOC triage path",
        ],
    },
}


def lookup(technique_string):
    """
    Accepts a technique string as produced by soc-triage-tool, e.g.
    "T1110.001 - Brute Force: Password Guessing", and returns the
    matching context dict, or None if not found.
    """
    if not technique_string:
        return None
    technique_id = technique_string.split(" - ")[0].strip()
    return ATTACK_TECHNIQUES.get(technique_id)
