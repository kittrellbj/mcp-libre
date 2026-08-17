from pathlib import Path
import zipfile

repoDir = Path(__file__).resolve().parent
pluginDir = repoDir / "plugin"
buildDir = repoDir / "build"
outputPath = buildDir / "libreoffice-mcp-extension-1.0.0.oxt"

buildDir.mkdir(parents=True, exist_ok=True)

files = [
    (pluginDir / "META-INF" / "manifest.xml", "META-INF/manifest.xml"),

    (pluginDir / "pythonpath" / "ai_interface.py", "pythonpath/ai_interface.py"),
    (pluginDir / "pythonpath" / "host_trust.py", "pythonpath/host_trust.py"),
    (pluginDir / "pythonpath" / "mcp_server.py", "pythonpath/mcp_server.py"),
    (pluginDir / "pythonpath" / "registration.py", "pythonpath/registration.py"),
    (pluginDir / "pythonpath" / "uno_bridge.py", "pythonpath/uno_bridge.py"),

    (pluginDir / "Addons.xcu", "Addons.xcu"),
    (pluginDir / "ProtocolHandler.xcu", "ProtocolHandler.xcu"),
    (pluginDir / "description.xml", "description.xml"),
    (pluginDir / "description-en.txt", "description-en.txt"),
    (pluginDir / "release-notes-en.txt", "release-notes-en.txt"),

    (repoDir / "LICENSE", "LICENSE"),
]

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
