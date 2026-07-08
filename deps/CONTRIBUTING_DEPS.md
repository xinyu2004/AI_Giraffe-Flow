# How to change dependencies

1. **Propose in `DEPENDENCIES.yaml`** — id, purpose, license, category (`runtime_board` / `host_tools` / `optional`).
2. **License check** — confirm SPDX OK for shipping on vehicle if `runtime_board`.
3. **Pin** — add exact tag/SHA to `versions.lock.md`.
4. **Integrate later** — `cmake_fetchcontent`, `system_package`, git submodule, or copy under `third_party/<id>/`.
5. **Profiles** — mark which of `desktop` / `board` / `vehicle-debug` / `production` enable it.
6. **Board CI** — host UI / ROS desktop deps must not enter board cross-builds.

Do **not** add undocumented packages only inside a single `CMakeLists.txt`.
