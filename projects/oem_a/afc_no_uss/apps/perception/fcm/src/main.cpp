#include "detect_backend.hpp"
#include "frame_source.hpp"

#include "gf_ara/com/binding/iceoryx/runtime.hpp"
#include "gf_ara/runtime/process_bringup.hpp"
#include "gf_gen/proxy/ego_motion_proxy.hpp"
#include "gf_gen/proxy/perception__in__st_proxy.hpp"
#include "gf_gen/skeleton/perception_message__out__st_skeleton.hpp"

#include "iceoryx_hoofs/posix_wrapper/signal_watcher.hpp"

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <optional>
#include <string>
#include <thread>

namespace {

constexpr const char* kProcess = "perception.fcm";

std::uint32_t EnvU32(const char* key, std::uint32_t def) {
  const char* v = std::getenv(key);
  if (!v || !v[0]) {
    return def;
  }
  return static_cast<std::uint32_t>(std::strtoul(v, nullptr, 10));
}

gf_gen::Perception_MESSAGE_Out_St MakeLegacyStubOut(std::uint64_t timestamp_ns,
                                                    std::uint64_t seq) {
  gf_gen::Perception_MESSAGE_Out_St out{};
  out.timestamp_ns = timestamp_ns;
  out.dyn_obj_count = static_cast<std::uint8_t>(1 + (seq % 3));
  out.static_obj_count = 1;
  out._vendor_payload_opaque[0] = 0;
  return out;
}

gf_gen::Perception_MESSAGE_Out_St MakeEmptyOut(std::uint64_t timestamp_ns) {
  gf_gen::Perception_MESSAGE_Out_St out{};
  out.timestamp_ns = timestamp_ns;
  out.dyn_obj_count = 0;
  out.static_obj_count = 0;
  out._vendor_payload_opaque[0] = 0;
  return out;
}

gf_gen::Perception_MESSAGE_Out_St MakeFromDetect(
    std::uint64_t timestamp_ns, const gf_fcm::DetectResult& d) {
  gf_gen::Perception_MESSAGE_Out_St out{};
  out.timestamp_ns = timestamp_ns;
  out.dyn_obj_count = d.dyn_obj_count;
  out.static_obj_count = d.static_obj_count;
  out._vendor_payload_opaque[0] = d.opaque;
  return out;
}

const char* KindName(gf_fcm::FrameSourceKind k) {
  switch (k) {
    case gf_fcm::FrameSourceKind::None:
      return "none";
    case gf_fcm::FrameSourceKind::Synth:
      return "synth";
    case gf_fcm::FrameSourceKind::File:
      return "file";
    case gf_fcm::FrameSourceKind::CarlaFile:
      return "carla_file";
  }
  return "?";
}

}  // namespace

int main() {
  gf_ara::com::binding::iceoryx::InitRuntime("gf-perception-fcm");

  gf_ara::runtime::ProcessSupervisor supervisor;
  if (!supervisor.Start(kProcess)) {
    return EXIT_FAILURE;
  }

  const auto frame_kind = gf_fcm::ParseFrameSource(nullptr);
  const auto backend = gf_fcm::ParseBackend(nullptr);
  const std::uint32_t timeout_ms = EnvU32("GF_FRAME_TIMEOUT_MS", 300);
  const std::uint32_t empty_period_ms = EnvU32("GF_EMPTY_PACKET_MS", 100);
  const char* model_env = std::getenv("GF_ONNX_MODEL");
  const std::string model_path = (model_env && model_env[0]) ? model_env : "";

  gf_fcm::FrameSource frames(frame_kind);
  gf_gen::Perception_In_StProxy in_sub{};
  gf_gen::EgoMotionProxy ego_sub{};
  gf_gen::Perception_MESSAGE_Out_StSkeleton out_pub{};

  std::uint64_t out_seq = 0;
  std::uint64_t last_frame_ns = 0;
  std::uint64_t last_empty_ns = 0;
  bool logged_timeout = false;

  std::cout << "gf-perception-fcm: start frame_source=" << KindName(frame_kind)
            << " backend="
            << (backend == gf_fcm::BackendKind::Onnx ? "onnx" : "stub")
            << " timeout_ms=" << timeout_ms << std::endl;

  while (!iox::posix::hasTerminationRequested()) {
    supervisor.Tick();
    if (supervisor.ExitForEmRestart()) {
      return gf_ara::exec::kEmRestartExitCode;
    }

    // Drain In (log alignment only when in frame mode).
    std::optional<std::uint32_t> in_frame;
    std::optional<std::uint64_t> in_ts;
    {
      auto taken = in_sub.Take();
      if (taken && taken.Value().has_value()) {
        in_frame = taken.Value()->ipc_frame_counter;
        in_ts = taken.Value()->timestamp_ns;
      }
    }

    if (frame_kind == gf_fcm::FrameSourceKind::None) {
      // Wave-A SIL stub: In-driven (+ EgoMotion fallback). Ego fabrication
      // is allowed only in this mode (plan lock).
      bool sent = false;
      if (in_ts.has_value()) {
        auto out = MakeLegacyStubOut(*in_ts, out_seq);
        if (static_cast<bool>(out_pub.Send(out))) {
          std::cout << "gf-perception-fcm: out#" << out_seq
                    << " dyn=" << static_cast<int>(out.dyn_obj_count)
                    << " frame=" << (in_frame ? *in_frame : 0) << std::endl;
          ++out_seq;
          sent = true;
        }
      }
      if (!sent) {
        auto ego_taken = ego_sub.Take();
        if (ego_taken && ego_taken.Value().has_value()) {
          const auto& ego = *ego_taken.Value();
          auto out = MakeLegacyStubOut(ego.timestamp_ns, out_seq);
          if (static_cast<bool>(out_pub.Send(out))) {
            std::cout << "gf-perception-fcm: out#" << out_seq
                      << " dyn=" << static_cast<int>(out.dyn_obj_count)
                      << " from=EgoMotion" << std::endl;
            ++out_seq;
          }
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
      continue;
    }

    // --- Frame tip mode: new frame → detect; timeout → periodic empty ---
    if (auto frame = frames.Poll()) {
      last_frame_ns = gf_fcm::FrameSource::NowNs();
      logged_timeout = false;
      gf_fcm::DetectResult det{};
      if (backend == gf_fcm::BackendKind::Onnx) {
        det = gf_fcm::DetectOnnxOrHeuristic(*frame, model_path);
      } else {
        det = gf_fcm::DetectStubFrame(*frame, out_seq);
      }
      const std::uint64_t ts =
          frame->meta.timestamp_ns != 0 ? frame->meta.timestamp_ns
                                        : (in_ts ? *in_ts : last_frame_ns);
      auto out = MakeFromDetect(ts, det);
      if (static_cast<bool>(out_pub.Send(out))) {
        std::cout << "gf-perception-fcm: out#" << out_seq
                  << " dyn=" << static_cast<int>(out.dyn_obj_count)
                  << " static=" << static_cast<int>(out.static_obj_count)
                  << " opaque=" << static_cast<int>(out._vendor_payload_opaque[0])
                  << " fseq=" << frame->meta.seq;
        if (in_frame) {
          std::cout << " in_frame=" << *in_frame;
        }
        std::cout << std::endl;
        ++out_seq;
      }
    } else {
      const std::uint64_t now = gf_fcm::FrameSource::NowNs();
      const bool never = (last_frame_ns == 0);
      const bool timed_out =
          never ||
          (now - last_frame_ns >=
           static_cast<std::uint64_t>(timeout_ms) * 1000000ULL);
      if (timed_out) {
        if (!logged_timeout) {
          std::cout << "gf-perception-fcm: "
                    << (never ? "no_frame" : "frame_timeout")
                    << " → empty packets" << std::endl;
          logged_timeout = true;
        }
        if (last_empty_ns == 0 ||
            (now - last_empty_ns >=
             static_cast<std::uint64_t>(empty_period_ms) * 1000000ULL)) {
          last_empty_ns = now;
          auto out = MakeEmptyOut(in_ts ? *in_ts : now);
          if (static_cast<bool>(out_pub.Send(out))) {
            std::cout << "gf-perception-fcm: out#" << out_seq
                      << " dyn=0 empty" << std::endl;
            ++out_seq;
          }
        }
      }
    }

    // Intentionally ignore EgoMotion for dyn fabrication in frame modes.
    (void)ego_sub.Take();
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return EXIT_SUCCESS;
}
