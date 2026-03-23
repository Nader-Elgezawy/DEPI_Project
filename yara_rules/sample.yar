/*
   Sample YARA rule — detects common suspicious strings.
   Replace or extend with your own rules.
*/

rule SuspiciousStrings
{
    meta:
        description = "Detects common suspicious strings in binaries"
        author      = "Forensics Dashboard Sample"
        date        = "2024-01-01"

    strings:
        $cmd1 = "cmd.exe" nocase
        $cmd2 = "/bin/sh" nocase
        $cmd3 = "powershell" nocase
        $net1 = "http://" nocase
        $net2 = "https://" nocase
        $reg1 = "HKEY_LOCAL_MACHINE" nocase
        $enc1 = "base64" nocase

    condition:
        any of them
}

rule PEExecutable
{
    meta:
        description = "Matches Windows PE executables"
        author      = "Forensics Dashboard Sample"

    condition:
        uint16(0) == 0x5A4D
}
