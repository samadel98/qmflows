# Bash script for downloading CP2K
#
# Usage: bash download_cp2k.sh ARCH VERSION OS EXEC
#
# VERSION is either a CP2K release (e.g. `9.1` or `2026.2`), whose pre-compiled binary is
# downloaded from GitHub, or `apt`/`brew`, which install whatever version the package manager ships.

set -euo pipefail

ARCH="$1"
VERSION="$2"
OS="$3"
EXEC="$4"

echo ::group::"Installing CP2K $ARCH $VERSION $OS $EXEC binaries"
case "$VERSION" in
    "apt")
        sudo apt-get update
        sudo apt-get install cp2k
        ;;
    "brew")
        brew install cp2k
        ;;
    *)
        # After the 9.1 release CP2K switched to a `<year>.<suffix>` version scheme (e.g. `2021.1`)
        if [[ $VERSION =~ [0-9][0-9][0-9][0-9]\.[0-9]+ ]]; then
            LINUX_PLAT="Linux-gnu"
            VERSION_LONG=v"$VERSION"
        else
            LINUX_PLAT="Linux"
            VERSION_LONG=v"$VERSION".0
        fi
        curl --version
        sudo curl -Lsf https://github.com/cp2k/cp2k/releases/download/$VERSION_LONG/cp2k-$VERSION-$LINUX_PLAT-$ARCH.$EXEC -o /usr/local/bin/cp2k.$EXEC
        sudo chmod a+rx /usr/local/bin/cp2k.$EXEC
        ;;
esac
echo ::endgroup::

# The data files (basis sets, pseudopotentials, etc.) have to match the CP2K version
CP2K_VERSION=$(cp2k.$EXEC --version | sed -n 's/^ *CP2K version \([0-9.]*\).*/\1/p' | head -n 1)
if [[ $CP2K_VERSION =~ [0-9][0-9][0-9][0-9]\.[0-9]+ ]]; then
    TAG=v"$CP2K_VERSION"
else
    TAG=v"$CP2K_VERSION".0
fi

echo ::group::"Get CP2K $CP2K_VERSION data"
git --version
git -c advice.detachedHead=false clone https://github.com/cp2k/cp2k -q --depth 1 --branch "$TAG" --filter=blob:none --sparse
git -C cp2k sparse-checkout set data
echo ::endgroup::
