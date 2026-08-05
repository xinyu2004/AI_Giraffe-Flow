#include "gf_ara/log/dlt_sink.hpp"

#include <cctype>
#include <mutex>
#include <string>
#include <unordered_map>

#if defined(GF_HAVE_DLT) && GF_HAVE_DLT
// COVESA BUILD_INTERFACE exports …/include/dlt (legacy path); use <dlt.h> not <dlt/dlt.h>.
#include <dlt.h>
#include <unistd.h>
#endif

namespace gf_ara::log {
namespace {

constexpr std::size_t kMaxContexts = 64;

#if defined(GF_HAVE_DLT) && GF_HAVE_DLT
// Our dlt-daemon build uses FIFO IPC at /tmp/dlt (see daemon log "FIFO").
constexpr const char* kDltUserFifo = "/tmp/dlt";

bool DaemonIpcPresent() {
  return ::access(kDltUserFifo, F_OK) == 0;
}
#endif

std::string FourId(std::string_view in) {
  std::string out(4, '_');
  std::size_t n = 0;
  for (char c : in) {
    if (n >= 4) {
      break;
    }
    if (std::isalnum(static_cast<unsigned char>(c))) {
      out[n++] = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
  }
  if (n == 0) {
    out = "GF__";
  }
  return out;
}

#if defined(GF_HAVE_DLT) && GF_HAVE_DLT
DltLogLevelType ToDltLevel(LogLevel level) {
  switch (level) {
    case LogLevel::kFatal:
      return DLT_LOG_FATAL;
    case LogLevel::kError:
      return DLT_LOG_ERROR;
    case LogLevel::kWarn:
      return DLT_LOG_WARN;
    case LogLevel::kInfo:
      return DLT_LOG_INFO;
    case LogLevel::kDebug:
      return DLT_LOG_DEBUG;
    case LogLevel::kVerbose:
      return DLT_LOG_VERBOSE;
  }
  return DLT_LOG_INFO;
}
#endif

}  // namespace

DltSink& DltSink::Instance() {
  static DltSink inst;
  return inst;
}

void DltSink::Configure(std::string_view app_id, std::string_view description) {
#if defined(GF_HAVE_DLT) && GF_HAVE_DLT
  static std::mutex mu;
  std::lock_guard lock(mu);
  if (!app_id.empty()) {
    app_id_ = std::string(app_id);
  }
  if (!description.empty()) {
    description_ = std::string(description);
  }
  if (ready_) {
    return;
  }
  // Root fix for ctest hang: never call dlt_register_app when daemon FIFO is missing
  // (libdlt otherwise blocks ~10s retrying the user↔daemon pipe).
  if (!DaemonIpcPresent()) {
    ready_ = false;
    return;
  }
  const std::string apid = FourId(app_id_);
  if (dlt_register_app(apid.c_str(), description_.c_str()) < DLT_RETURN_OK) {
    ready_ = false;
    return;
  }
  ready_ = true;
#else
  (void)app_id;
  (void)description;
  ready_ = false;
#endif
}

void DltSink::Write(std::string_view ctx, LogLevel level, std::string_view msg) {
#if defined(GF_HAVE_DLT) && GF_HAVE_DLT
  if (!ready_) {
    // Lazy retry when daemon appears after process start.
    Configure(app_id_, description_);
    if (!ready_) {
      return;
    }
  }
  static std::mutex mu;
  static std::unordered_map<std::string, DltContext> contexts;
  std::lock_guard lock(mu);

  const std::string key(ctx);
  auto it = contexts.find(key);
  if (it == contexts.end()) {
    if (contexts.size() >= kMaxContexts) {
      it = contexts.find("__ov");
      if (it == contexts.end()) {
        DltContext ov{};
        if (dlt_register_context(&ov, "OVFL", "context overflow") < DLT_RETURN_OK) {
          return;
        }
        it = contexts.emplace("__ov", ov).first;
      }
    } else {
      DltContext handle{};
      const std::string ctxid = FourId(ctx);
      const std::string desc(ctx);
      if (dlt_register_context(&handle, ctxid.c_str(), desc.c_str()) < DLT_RETURN_OK) {
        return;
      }
      it = contexts.emplace(key, handle).first;
    }
  }

  const std::string text(msg);
  (void)dlt_log_string(&it->second, ToDltLevel(level), text.c_str());
#else
  (void)ctx;
  (void)level;
  (void)msg;
#endif
}

}  // namespace gf_ara::log
