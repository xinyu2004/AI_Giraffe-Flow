# Runtime layout contract:
#   staged:  runtime/bin/* + runtime/lib/*.so  → INSTALL_RPATH $ORIGIN:$ORIGIN/../lib
#   build:   ${CMAKE_BINARY_DIR}/lib/*.so      → BUILD_RPATH absolute (ctest / ldd)
#
# Do NOT set CMAKE_BUILD_WITH_INSTALL_RPATH — that made smoke tests look for
# $ORIGIN/../lib while libs still lived under middleware/<mod>/ (or now build/lib).

set(CMAKE_BUILD_RPATH_USE_ORIGIN ON)
set(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
set(CMAKE_SKIP_BUILD_RPATH FALSE)
set(CMAKE_INSTALL_RPATH "$ORIGIN:$ORIGIN/../lib")
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH FALSE)

# One directory for all Giraffe SHARED libs so BUILD_RPATH / $ORIGIN work.
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

# Absolute build RPATH so middleware/*/smoke and deep app trees resolve libs +
# transitive deps (CMake also appends directories of linked shared libs, e.g. libdlt).
set(CMAKE_BUILD_RPATH "${CMAKE_BINARY_DIR}/lib")
