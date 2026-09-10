#pragma once

// Per-port identity (Error) + publish_policy budget (Warn).
// Identity: seq gap / rewind / dup / reused timestamp.
// Budget: on_change expect_fps = 5s window vs expect/2 and camera ceiling;
//         period silence = 10 cycles on TX period ports only (not RX, not average vs 100 Hz).
// Uneven actual cadence is OK. No freeze. Console + DLT when sinks exist.

#include "gf_ara/log/logger.hpp"
#include "gf_gen/publish_policy.hpp"
#include "gf_gen/frame_ingest_config.hpp"

#include <chrono>
#include <cstdint>
#include <sstream>
#include <string>
#include <string_view>

namespace gf_app {

inline std::uint64_t WatchWallNs() {
  using clock = std::chrono::steady_clock;
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(clock::now().time_since_epoch())
          .count());
}

inline void EnsureDiagLogSinks() {
  auto& log = gf_ara::log::Logger::Instance();
  auto cfg = log.Config();
  bool has_dlt = false;
  bool has_cons = false;
  for (const auto& s : cfg.sinks) {
    if (s == "dlt") {
      has_dlt = true;
    }
    if (s == "console" || s == "stdout" || s == "stderr") {
      has_cons = true;
    }
  }
  bool changed = false;
  if (!has_cons) {
    cfg.sinks.push_back("console");
    changed = true;
  }
  if (!has_dlt) {
    cfg.sinks.push_back("dlt");
    changed = true;
  }
  if (changed) {
    log.Configure(cfg);
  }
}

struct FrameWatch {
  const char* ctx{"frame"};
  const char* port{"?"};
  std::uint64_t last_seq{0};
  std::uint64_t last_ts{0};
  std::uint64_t last_emit_wall{0};
  std::uint64_t last_sum_wall{0};
  std::uint32_t emit_burst{0};
  bool have{false};
  std::uint64_t n_ok{0};
  std::uint64_t n_gap{0};
  std::uint64_t n_dup{0};
  std::uint64_t n_rewind{0};
  std::uint64_t n_stale_ts{0};
  std::uint32_t period_ms{0};
  std::uint32_t expect_fps{0};
  std::uint32_t camera_fps{0};
  bool period_silence{false};
  std::uint64_t last_obs_wall{0};
  std::uint64_t win_start_wall{0};
  std::uint32_t win_n{0};
  std::uint64_t n_silence{0};
  std::uint64_t n_slow{0};
  std::uint64_t n_over_cam{0};
  std::uint64_t sum_ok{0};
  std::uint64_t sum_gap{0};
  std::uint64_t sum_dup{0};
  std::uint64_t sum_rewind{0};
  std::uint64_t sum_stale_ts{0};
  std::uint64_t sum_silence{0};
  std::uint64_t sum_slow{0};
  std::uint64_t sum_over_cam{0};

  void Init(const char* log_ctx, const char* port_name) {
    ctx = log_ctx;
    port = port_name;
  }

  void BindService(const char* id) {
    BindPolicy(gf_gen::publish_policy::FindService(id));
  }

  void BindChannel(const char* id) {
    BindPolicy(gf_gen::publish_policy::FindChannel(id));
  }

  void BindCameraCeiling() { camera_fps = gf_gen::frame_ingest::kCameraFpsFront; }

  void EnablePeriodSilence() { period_silence = true; }

  void BindPolicy(const gf_gen::publish_policy::TopicPolicy* p) {
    if (!p || !p->id || !p->id[0]) {
      return;
    }
    period_ms = p->period_ms;
    expect_fps = p->expect_fps;
  }

  std::string PolicyHint() const {
    std::ostringstream oss;
    if (period_ms > 0) {
      oss << "period_ms=" << period_ms;
      if (period_silence) {
        oss << "(tx-silence)";
      }
    }
    if (expect_fps > 0) {
      if (oss.tellp() > 0) {
        oss << " ";
      }
      oss << "expect_fps=" << expect_fps;
    }
    if (camera_fps > 0) {
      if (oss.tellp() > 0) {
        oss << " ";
      }
      oss << "camera_fps=" << camera_fps;
    }
    if (oss.tellp() == 0) {
      return "budget=none";
    }
    return oss.str();
  }

  void Reset() {
    have = false;
    last_seq = 0;
    last_ts = 0;
    last_obs_wall = 0;
    win_start_wall = 0;
    win_n = 0;
  }

  bool RateOk() {
    const std::uint64_t now = WatchWallNs();
    if (last_emit_wall != 0 && now - last_emit_wall < 125000000ULL) {
      ++emit_burst;
      if (emit_burst > 8) {
        return false;
      }
    } else {
      emit_burst = 0;
      last_emit_wall = now;
    }
    return true;
  }

  void Error(std::string_view msg) {
    if (!RateOk()) {
      return;
    }
    gf_ara::log::Logger::Instance().Error(ctx, std::string(port) + " " + std::string(msg));
  }

  void Warn(std::string_view msg) {
    if (!RateOk()) {
      return;
    }
    gf_ara::log::Logger::Instance().Warn(ctx, std::string(port) + " " + std::string(msg));
  }

  static std::uint64_t SilenceNs(std::uint64_t budget_ns) {
    const std::uint64_t n = budget_ns * 10ULL;
    return n < 100000000ULL ? 100000000ULL : n;
  }

  std::uint64_t GapBudgetNs() const {
    if (period_silence && period_ms > 0) {
      return static_cast<std::uint64_t>(period_ms) * 1000000ULL;
    }
    if (expect_fps > 0) {
      return 1000000000ULL / static_cast<std::uint64_t>(expect_fps);
    }
    return 0;
  }

  void FlushRateWindow(std::uint64_t wall) {
    if (expect_fps == 0 || win_start_wall == 0 || wall <= win_start_wall) {
      win_start_wall = wall;
      win_n = 0;
      return;
    }
    const double elapsed_s =
        static_cast<double>(wall - win_start_wall) / 1000000000.0;
    if (elapsed_s < 1.0) {
      return;
    }
    const double fps = static_cast<double>(win_n) / elapsed_s;
    if (fps < static_cast<double>(expect_fps) * 0.5) {
      ++n_slow;
      std::ostringstream oss;
      oss << "too_slow fps=" << fps << " expect_fps=" << expect_fps
          << " (window " << elapsed_s << "s; actual cadence, not a send clock)";
      Warn(oss.str());
    }
    if (camera_fps > 0 && fps > static_cast<double>(camera_fps)) {
      ++n_over_cam;
      std::ostringstream oss;
      oss << "above_camera fps=" << fps << " camera_fps=" << camera_fps
          << " (Out Hz must be ≤ camera)";
      Warn(oss.str());
    }
    win_start_wall = wall;
    win_n = 0;
  }

  void NoteRate(std::uint64_t wall) {
    const std::uint64_t budget = GapBudgetNs();
    if (budget != 0 && last_obs_wall != 0 && wall > last_obs_wall) {
      const std::uint64_t dt = wall - last_obs_wall;
      if (dt > SilenceNs(budget)) {
        ++n_silence;
        std::ostringstream oss;
        oss << "silence dt_ms=" << (dt / 1000000ULL)
            << " budget_ms=" << (budget / 1000000ULL)
            << " (10× cycle / expect interval, floor 100ms)";
        Warn(oss.str());
      }
    }
    last_obs_wall = wall;
    if (expect_fps == 0) {
      return;
    }
    if (win_start_wall == 0) {
      win_start_wall = wall;
      win_n = 1;
      return;
    }
    ++win_n;
    if (wall - win_start_wall >= 5000000000ULL) {
      FlushRateWindow(wall);
    }
  }

  void MaybeSummary(std::uint64_t wall) {
    if (last_sum_wall == 0) {
      last_sum_wall = wall;
      return;
    }
    if (wall - last_sum_wall < 5000000000ULL) {
      return;
    }
    last_sum_wall = wall;
    const std::uint64_t d_ok = n_ok - sum_ok;
    const std::uint64_t d_gap = n_gap - sum_gap;
    const std::uint64_t d_dup = n_dup - sum_dup;
    const std::uint64_t d_rewind = n_rewind - sum_rewind;
    const std::uint64_t d_stale = n_stale_ts - sum_stale_ts;
    const std::uint64_t d_silence = n_silence - sum_silence;
    const std::uint64_t d_slow = n_slow - sum_slow;
    const std::uint64_t d_over = n_over_cam - sum_over_cam;
    sum_ok = n_ok;
    sum_gap = n_gap;
    sum_dup = n_dup;
    sum_rewind = n_rewind;
    sum_stale_ts = n_stale_ts;
    sum_silence = n_silence;
    sum_slow = n_slow;
    sum_over_cam = n_over_cam;
    if (d_gap + d_dup + d_rewind + d_stale > 0) {
      std::ostringstream oss;
      oss << "summary ok=" << d_ok << " gap=" << d_gap << " dup=" << d_dup
          << " rewind=" << d_rewind << " same_ts=" << d_stale;
      gf_ara::log::Logger::Instance().Error(ctx, std::string(port) + " " + oss.str());
    }
    if (d_silence + d_slow + d_over > 0) {
      std::ostringstream oss;
      oss << "budget " << PolicyHint() << " silence=" << d_silence
          << " too_slow=" << d_slow << " above_camera=" << d_over;
      gf_ara::log::Logger::Instance().Warn(ctx, std::string(port) + " " + oss.str());
    }
  }

  // have_seq: payload/channel sequence. have_ts: producer timestamp_ns.
  void Observe(std::uint64_t seq, std::uint64_t ts_ns, bool have_seq = true,
               bool have_ts = true) {
    const std::uint64_t wall = WatchWallNs();
    if (!have) {
      have = true;
      last_seq = seq;
      last_ts = ts_ns;
      last_sum_wall = wall;
      last_obs_wall = wall;
      win_start_wall = wall;
      win_n = 1;
      ++n_ok;
      return;
    }

    std::ostringstream oss;
    bool defensive = false;
    if (have_seq) {
      if (seq == last_seq) {
        ++n_dup;
        defensive = true;
        oss << "dup seq=" << seq;
      } else if (seq < last_seq) {
        ++n_rewind;
        defensive = true;
        oss << "rewind seq=" << last_seq << "->" << seq;
      } else if (seq > last_seq + 1) {
        const std::uint64_t skip = seq - last_seq - 1;
        n_gap += skip;
        defensive = true;
        oss << "gap seq=" << last_seq << "->" << seq << " skipped=" << skip
            << " (overlay-latest or drop)";
      }
    }
    if (have_ts && ts_ns != 0 && last_ts != 0 && ts_ns == last_ts) {
      ++n_stale_ts;
      defensive = true;
      if (oss.tellp() > 0) {
        oss << " ";
      }
      oss << "same_ts_ns=" << ts_ns;
      if (have_seq && seq != last_seq) {
        oss << " seq=" << last_seq << "->" << seq;
      }
    }
    if (defensive) {
      Error(oss.str());
    } else {
      ++n_ok;
    }
    last_seq = seq;
    last_ts = ts_ns;
    NoteRate(wall);
    MaybeSummary(wall);
  }
};

}  // namespace gf_app
