from pathlib import Path
import zipfile

repoDir = Path(__file__).resolve().parent
pluginDir = repoDir / "plugin"
buildDir = repoDir / "build"
outputPath = buildDir / "libreoffice-mcp-extension-2.0.4.oxt"

buildDir.mkdir(parents=True, exist_ok=True)

files = [
    (pluginDir / "META-INF" / "manifest.xml", "META-INF/manifest.xml"),

    (pluginDir / "Addons.xcu", "Addons.xcu"),
    (pluginDir / "ProtocolHandler.xcu", "ProtocolHandler.xcu"),
    (pluginDir / "description.xml", "description.xml"),
    (pluginDir / "description-en.txt", "description-en.txt"),
    (pluginDir / "release-notes-en.txt", "release-notes-en.txt"),

    (repoDir / "LICENSE", "LICENSE"),
]

# Every pythonpath/*.py module, plus the whole tools/ package, is globbed
# in rather than hand-listed -- a hand-maintained list silently goes stale
# the moment a new module is added (this bit twice: the tools/ package
# was missing entirely until Phase A+D's real-implementation pass, then
# uno_datetime.py was nearly missed the same way immediately after fixing
# that). Every one of these is a hard import of mcp_server.py or something
# it imports, so shipping the .oxt without one breaks the extension the
# moment LibreOffice loads it. Excludes __pycache__ (never wanted here).
pythonpathDir = pluginDir / "pythonpath"
for sourcePath in sorted(pythonpathDir.glob("*.py")):
    files.append((sourcePath, f"pythonpath/{sourcePath.name}"))
for sourcePath in sorted((pythonpathDir / "tools").glob("*.py")):
    files.append((sourcePath, f"pythonpath/tools/{sourcePath.name}"))

missingFiles = [
    str(sourcePath)
    for sourcePath, archiveName in files
    if not sourcePath.is_file()
]

if missingFiles:
    raise FileNotFoundError(
        "Missing required extension files:\n" +
        "\n".join(missingFiles)
    )

if outputPath.exists():
    outputPath.unlink()

with zipfile.ZipFile(
    outputPath,
    mode="w",
    compression=zipfile.ZIP_DEFLATED,
    compresslevel=9,
) as archive:
    for sourcePath, archiveName in files:
        # LibreOffice expects normalized ZIP entry names.
        archiveName = archiveName.replace("\\", "/")

        if (
            archiveName.startswith("/")
            or "\\" in archiveName
            or ":" in archiveName
            or ".." in archiveName.split("/")
        ):
            raise ValueError(f"Invalid archive name: {archiveName}")

        archive.write(sourcePath, arcname=archiveName)

# Validate resulting ZIP.
with zipfile.ZipFile(outputPath, "r") as archive:
    badFile = archive.testzip()

    if badFile:
        raise RuntimeError(f"CRC failure in archive: {badFile}")

    print(f"Built: {outputPath}")
    print()
    print("Archive entries:")

    for name in archive.namelist():
        print(repr(name))

print()
print(f"Size: {outputPath.stat().st_size:,} bytes")
