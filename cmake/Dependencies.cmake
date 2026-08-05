# Resolve board/runtime third-party deps declared in dep-manifest/DEPENDENCIES.yaml.
#
# Policy (P0+): runtime deps are built from source with the active toolchain.
#   - attr/acl → scripts/bootstrap_deps.sh installs into middleware/.deps-prefix/
#   - iceoryx  → middleware/third_party/iceoryx via add_subdirectory (same CMAKE_TOOLCHAIN_FILE)
# Do NOT treat apt libacl1-dev as the board/cross path.

set(GF_THIRD_PARTY_DIR "${CMAKE_SOURCE_DIR}/middleware/third_party" CACHE PATH "Vendored upstream trees")
set(GF_DEPS_PREFIX "${CMAKE_SOURCE_DIR}/middleware/.deps-prefix" CACHE PATH "Staging prefix for source-built deps (attr/acl)")

# --- ACL from source staging (required when GF_WITH_ICEORYX) ---
set(_gf_acl_hdr "${GF_DEPS_PREFIX}/include/sys/acl.h")
if(EXISTS "${_gf_acl_hdr}")
  include_directories(BEFORE SYSTEM "${GF_DEPS_PREFIX}/include")
  link_directories("${GF_DEPS_PREFIX}/lib")
  list(APPEND CMAKE_PREFIX_PATH "${GF_DEPS_PREFIX}")
  message(STATUS "Giraffe Flow: ACL from source prefix ${GF_DEPS_PREFIX}")
elseif(GF_WITH_ICEORYX OR EXISTS "${GF_THIRD_PARTY_DIR}/iceoryx/iceoryx_meta/CMakeLists.txt")
  # Will enable iceoryx below; fail early with a clear action.
  if(NOT EXISTS "${_gf_acl_hdr}")
    message(WARNING
      "Giraffe Flow: ${_gf_acl_hdr} missing.\n"
      "  Run: bash scripts/bootstrap_deps.sh\n"
      "  (builds attr+acl from source into middleware/.deps-prefix; same path for cross via GF_CROSS_PREFIX=...)")
  endif()
endif()

# --- iceoryx classic C++ (pin: dep-manifest/versions.lock.md) ---
set(_gf_iox_root "${GF_THIRD_PARTY_DIR}/iceoryx")
set(_gf_iox_meta "${_gf_iox_root}/iceoryx_meta")

# Auto-enable when sources exist, unless forced OFF / SKU already decided off.
if(EXISTS "${_gf_iox_meta}/CMakeLists.txt")
  if(GF_FORCE_NO_ICEORYX)
    message(STATUS "Giraffe Flow: iceoryx present but GF_FORCE_NO_ICEORYX=ON")
  elseif(GF_WITH_ICEORYX)
    # already on (CLI or SKU)
  elseif(GF_SKU_APPLIED)
    message(STATUS "Giraffe Flow: SKU applied; GF_WITH_ICEORYX=${GF_WITH_ICEORYX}")
  else()
    message(STATUS "Giraffe Flow: found ${_gf_iox_meta}; enabling GF_WITH_ICEORYX")
    set(GF_WITH_ICEORYX ON CACHE BOOL "Build iceoryx binding" FORCE)
  endif()
elseif(GF_WITH_ICEORYX)
  message(FATAL_ERROR
    "GF_WITH_ICEORYX=ON but ${_gf_iox_meta} is missing.\n"
    "Run: bash scripts/bootstrap_deps.sh")
endif()

if(GF_WITH_ICEORYX)
  if(NOT EXISTS "${_gf_acl_hdr}")
    message(FATAL_ERROR
      "GF_WITH_ICEORYX=ON requires source-built ACL at:\n"
      "  ${_gf_acl_hdr}\n"
      "Run: bash scripts/bootstrap_deps.sh\n"
      "Cross: GF_CROSS_PREFIX=aarch64-linux-gnu bash scripts/bootstrap_deps.sh")
  endif()

  set(EXAMPLES OFF CACHE BOOL "" FORCE)
  set(BUILD_TEST OFF CACHE BOOL "" FORCE)
  set(INTROSPECTION OFF CACHE BOOL "" FORCE)
  set(DDS_GATEWAY OFF CACHE BOOL "" FORCE)
  set(BINDING_C OFF CACHE BOOL "" FORCE)
  set(DOWNLOAD_TOML_LIB ON CACHE BOOL "" FORCE)

  add_subdirectory("${_gf_iox_meta}" "${CMAKE_BINARY_DIR}/_dep-manifest/iceoryx_meta" EXCLUDE_FROM_ALL)
  set(GF_ICEORYX_FOUND TRUE)
  message(STATUS "Giraffe Flow: iceoryx from ${_gf_iox_root} (via iceoryx_meta)")
else()
  set(GF_ICEORYX_FOUND FALSE)
  message(STATUS "Giraffe Flow: iceoryx disabled (run bash scripts/bootstrap_deps.sh then reconfigure)")
endif()

# --- CycloneDDS (optional; default vendor when GF_WITH_DDS) ---
# Source tree: middleware/third_party/cyclonedds (pin: dep-manifest/versions.lock.md).
# Offline CI uses bindings/dds stub backend; add_subdirectory only when present.
set(_gf_cdds_root "${GF_THIRD_PARTY_DIR}/cyclonedds")
set(GF_CYCLONEDDS_FOUND FALSE)
if(GF_WITH_DDS AND EXISTS "${_gf_cdds_root}/CMakeLists.txt")
  set(BUILD_IDLC ON CACHE BOOL "" FORCE)
  set(ENABLE_TOPIC_DISCOVERY ON CACHE BOOL "" FORCE)
  set(ENABLE_SECURITY OFF CACHE BOOL "" FORCE)
  set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
  add_subdirectory("${_gf_cdds_root}" "${CMAKE_BINARY_DIR}/_dep-manifest/cyclonedds" EXCLUDE_FROM_ALL)
  set(GF_CYCLONEDDS_FOUND TRUE)
  message(STATUS "Giraffe Flow: CycloneDDS from ${_gf_cdds_root}")
elseif(GF_WITH_DDS)
  message(STATUS
    "Giraffe Flow: CycloneDDS sources not under ${_gf_cdds_root}; "
    "DDS binding uses stub backend (default offline)")
endif()

# --- COVESA DLT (libdlt + dlt-daemon); pin: dep-manifest/versions.lock.md ---
# Source: middleware/third_party/dlt-daemon via bootstrap_deps.sh (not apt).
set(_gf_dlt_root "${GF_THIRD_PARTY_DIR}/dlt-daemon")
set(GF_DLT_FOUND FALSE)
if(GF_FORCE_NO_DLT)
  set(GF_WITH_DLT OFF CACHE BOOL "Build/link COVESA DLT (libdlt + dlt-daemon)" FORCE)
  message(STATUS "Giraffe Flow: GF_FORCE_NO_DLT=ON → DLT OFF")
elseif(EXISTS "${_gf_dlt_root}/CMakeLists.txt")
  if(NOT GF_WITH_DLT)
    message(STATUS "Giraffe Flow: dlt-daemon present but GF_WITH_DLT=OFF")
  endif()
elseif(GF_WITH_DLT)
  message(WARNING
    "GF_WITH_DLT=ON but ${_gf_dlt_root} missing.\n"
    "  Run: bash scripts/bootstrap_deps.sh")
endif()

if(GF_WITH_DLT AND EXISTS "${_gf_dlt_root}/CMakeLists.txt")
  set(WITH_DLT_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_TESTS OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_UNIT_TESTS OFF CACHE BOOL "" FORCE)
  set(WITH_DOC OFF CACHE BOOL "" FORCE)
  set(WITH_MAN OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_SYSTEM OFF CACHE BOOL "" FORCE)
  set(WITH_SYSTEMD OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_ADAPTOR OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_ADAPTOR_STDIN OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_ADAPTOR_UDP OFF CACHE BOOL "" FORCE)
  set(WITH_DLT_CONSOLE ON CACHE BOOL "" FORCE)
  # Prefer shared libdlt for SIL RPATH; restore after add_subdirectory so iceoryx/etc. unchanged.
  set(_gf_dlt_saved_shared "${BUILD_SHARED_LIBS}")
  set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
  # Upstream enables -Werror; newer GCC trips on discarded-qualifiers in dlt_common.c
  set(_gf_dlt_saved_c_flags "${CMAKE_C_FLAGS}")
  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wno-error=discarded-qualifiers -Wno-error")
  add_subdirectory("${_gf_dlt_root}" "${CMAKE_BINARY_DIR}/_dep-manifest/dlt-daemon")
  set(CMAKE_C_FLAGS "${_gf_dlt_saved_c_flags}")
  if(DEFINED _gf_dlt_saved_shared)
    set(BUILD_SHARED_LIBS "${_gf_dlt_saved_shared}" CACHE BOOL "" FORCE)
  endif()
  if(TARGET dlt)
    set(GF_DLT_FOUND TRUE CACHE BOOL "COVESA libdlt available" FORCE)
    message(STATUS "Giraffe Flow: DLT from ${_gf_dlt_root} (libdlt + dlt-daemon)")
  else()
    message(WARNING "Giraffe Flow: dlt-daemon subtree present but target 'dlt' missing")
  endif()
else()
  set(GF_DLT_FOUND FALSE CACHE BOOL "COVESA libdlt available" FORCE)
  message(STATUS "Giraffe Flow: DLT disabled (bootstrap dlt-daemon → middleware/third_party/dlt-daemon)")
endif()
